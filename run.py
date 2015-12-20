#!/usr/bin/env python

import requests
import json
import re
import os
import logging
import motor.motor_asyncio
import pymongo
import asyncio
import websockets



class GhostApp:
    EVENT_HANDLERS = {
        'hello': 'report',
        'message': 'handle_message',
        'user_typing': 'ignore',
        'channel_marked': 'report',
        'channel_created': 'report',
        'channel_joined': 'report',
        'channel_left': 'report',
        'channel_deleted': 'report',
        'channel_rename': 'report',
        'channel_archive': 'report',
        'channel_unarchive': 'report',
        'channel_history_changed': 'report',
        'im_created': 'report',
        'im_open': 'report',
        'im_close': 'report',
        'im_marked': 'report',
        'im_history_changed': 'report',
        'group_joined': 'report',
        'group_left': 'report',
        'group_open': 'report',
        'group_close': 'report',
        'group_archive': 'report',
        'group_unarchive': 'report',
        'group_rename': 'report',
        'group_marked': 'report',
        'group_history_changed': 'report',
        'file_created': 'archive',
        'file_shared': 'archive',
        'file_unshared': 'archive',
        'file_public': 'archive',
        'file_private': 'archive',
        'file_change': 'archive',
        'file_deleted': 'archive',
        'file_comment_added': 'archive',
        'file_comment_edited': 'archive',
        'file_comment_deleted': 'archive',
        'pin_added': 'report',
        'pin_removed': 'report',
        'presence_change': 'report',
        'manual_presence_change': 'report',
        'pref_change': 'report',
        'user_change': 'refresh',
        'team_join': 'refresh',
        'star_added': 'archive',
        'star_removed': 'archive',
        'reaction_added': 'archive',
        'reaction_removed': 'archive',
        'emoji_changed': 'ignore',
        'commands_changed': 'ignore',
        'team_plan_change': 'ignore',
        'team_pref_change': 'refresh',
        'team_rename': 'refresh',
        'team_domain_change': 'refresh',
        'email_domain_changed': 'refresh',
        'bot_added': 'refresh',
        'bot_changed': 'refresh',
        'accounts_changed': 'refresh',
        'team_migration_started': 'report',
        'subteam_created': 'archive',
        'subteam_updated': 'archive',
        'subteam_self_added': 'report',
        'subteam_self_removed': 'report',
        'pong': 'pong'
    }

    API_URL = 'https://slack.com/api/'

    def __init__(self):
        self.config = {
            'DB_URI': 'mongodb://localhost:27017',
            'DB_NAME': 'ghost',
            'TOKEN': None,
            'DEBUG': False,
            'PING_ENABLED': True,
            'CHANNELS': []
        }
        self.websocket_url = None
        self.user_id = None
        self.loop = None
        self.db = None
        self.EVENT_HANDLERS = {k: getattr(self, v) for k, v in self.EVENT_HANDLERS.items()}

        self._ping_handle = None
        self._pings = {}

    def load_config(self, path):
        from importlib.machinery import SourceFileLoader
        try:
            conf = SourceFileLoader('conf', path).load_module()
            for key in dir(conf):
                if key.isupper():
                    self.config[key] = getattr(conf, key)
        except FileNotFoundError:
            print('Config file not found')

    def _method_url(self, name):
        return self.API_URL + name

    def init_logging(self):
        self.log = logging.getLogger('ghost')
        self.log.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()

        if self.config['DEBUG']:
            console_handler.setLevel(logging.DEBUG)
        else:
            console_handler.setLevel(logging.ERROR)

        formatter = logging.Formatter('%(asctime)s %(levelname)s: \033[33m%(message)s\033[0m [in %(pathname)s:%(lineno)d]')
        console_handler.setFormatter(formatter)

        self.log.addHandler(console_handler)

    def init_db(self):
        client = pymongo.MongoClient(self.config["DB_URI"])
        client.ghost.event_log.create_index([('ts', pymongo.ASCENDING)])
        client.ghost.event_log.create_index([('text', pymongo.TEXT)], default_language='russian', background=True)

    def before_run(self):
        self.init_logging()
        self.init_db()

    def _parse_rtm_start(self, response):
        by_name = {c['name']: c['id'] for c in response['channels']}

        self.channels = []
        for c in self.config['CHANNELS']:
            if c in by_name:
                self.channels.append(by_name[c])
            else:
                self.channels.append(c)

        self.websocket_url = response['url']
        self.user_id = response['self']['id']

    def run(self):
        self.before_run()

        if not self.config['TOKEN']:
            self.log.critical('Authentication token not set')
            return

        self.db_instance = motor.motor_asyncio.AsyncIOMotorClient(self.config['DB_URI'])
        self.db = self.db_instance[self.config['DB_NAME']]

        response = requests.get(self._method_url('rtm.start'), params={'token': self.config['TOKEN']})

        if response.status_code == 200:
            r = json.loads(response.text)
            if r.get('ok'):
                self.log.info('Slack API responded')
                self._parse_rtm_start(r)
                self.loop = asyncio.get_event_loop()
                self.loop.run_until_complete(self.listen())
            else:
                self.log.error('rtm.start failed with error: {}'.format(r.get('error')))
        else:
            self.log.error('rtm.start failed with status code {}'.format(response.status_code))

    async def listen(self):
        self.websocket = await websockets.connect(self.websocket_url)

        self.log.info('Connection established. Listening for events...')

        while True:
            if self.config['PING_ENABLED']:
                self._ping_handle = self.loop.call_later(5, self.ping)

            event_json = await self.websocket.recv()

            if self.config['PING_ENABLED']:
                self._ping_handle.cancel()

            event = json.loads(event_json)
            event_type = event.get('type')

            if event_type:
                try:
                    action = self.EVENT_HANDLERS[event_type]
                except KeyError:
                    self.log.error('Unknown envent type {} in event {}'.format(event_type, event))
            
                message = action(event)
                if message:
                    await self.websocket.send(message)

        await self.websocket.close()

    def ping(self):
        if len(self._pings) > 0:
            self.log.warning('Ping did not return within a given timeout')
            # TODO: handle ping fails
        else:
            ping_id = int(self.loop.time())
            self._pings[ping_id] = True

            msg = json.dumps({'id': ping_id, 'type': 'ping'})
            asyncio.ensure_future(self.websocket.send(msg))
            self._ping_handle = self.loop.call_later(5, self.ping)
            self.log.debug('Ping: {}'.format(msg))

    def ignore(self, event):
        self.log.debug('Event ignored: {}'.format(event))

    def report(self, event):
        self.log.info('Event report: {}'.format(event))

    def archive(self, event):
        asyncio.ensure_future(self.store_event(event))

    async def store_event(self, event):
        if event['ts']:
            event['ts'] = float(event['ts'])
            result = await self.db.event_log.insert(event)
            if not result:
                self.log.error('Database insert failed with error {}:{}'.format(
                    result.writeError.code, result.writeError.errmsg))
        else:
            self.log.warning('Event does not have a timestamp and will be skipped: {}'.format(event))

    def handle_message(self, event):
        channel = event.get('channel')
        if channel not in self.channels:
            return

        text = event.get('text')
        user = event.get('user')

        self.archive(event)

        if text and user and re.search('<@{}>'.format(self.user_id), text):
            message = json.dumps({
                'type': 'message',
                'channel': event['channel'],
                'text': 'привет <@{}>'.format(user)
            })
            return message

    def refresh(self):
        # TODO: reload main info
        pass

    def pong(self, event):
        self._pings.pop(event.get('reply_to'))
        self.log.debug('Pong: {}'.format(event))


def main():
    app = GhostApp()
    app.load_config('ghost.conf')
    app.run()


if __name__ == '__main__':
    main()
