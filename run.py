#!/usr/bin/env python

import requests
import json
import time
import re
import signal
import os
from functools import partial
from pprint import pprint

import asyncio
import websockets


API_URL = 'https://slack.com/api/'

class Shutdown(Exception):
    pass


ping_handle = None
pings = {}
config = None

user_id = None


def ignore(event):
    pass


def report(event):
    print(event)


def archive(event):
    with open(config.log, 'a') as f:
        f.write(str(event) + '\n')


def handle_message(event):
    text = event.get('text')
    user = event.get('user')

    archive(event)

    if text and user and re.search('<@{}>'.format(user_id), text):
        message = json.dumps({
            'type': 'message',
            'channel': event['channel'],
            'text': 'привет <@{}>'.format(user)
        })
        return message


def refresh():
    pass


def pong(event):
    pings.pop(event.get('reply_to'))


def method_url(name):
    return API_URL + name


def ping(loop, websocket):
    global ping_handle

    if len(pings) > 0:
        # опа, за 5 сек pong не вернулся
        print('alarm!')
    else:
        ping_id = int(loop.time())
        pings[ping_id] = True

        msg = json.dumps({'id': ping_id, 'type': 'ping'})
        asyncio.ensure_future(websocket.send(msg))
        ping_handle = loop.call_later(5, ping, loop, websocket)


async def listen(url, loop):
    global ping_handle

    websocket = await websockets.connect(url)

    while True:
        ping_handle = loop.call_later(5, ping, loop, websocket)
        event_json = await websocket.recv()
        ping_handle.cancel()

        event = json.loads(event_json)
        event_type = event.get('type')

        if event_type:
            try:
                action = EVENT_TYPES[event_type]['action']
            except KeyError:
                print('Unknown envent type {} in event {}'.format(event_type, event))
        
            message = action(event)
            if message:
                await websocket.send(message)

    await websocket.close()


def load_config():
    from importlib.machinery import SourceFileLoader
    try:
        conf = SourceFileLoader('conf', 'ghost.conf').load_module()
        return conf
    except FileNotFoundError:
        print('Config not found')


def main():
    global user_id
    global config

    config = load_config()

    d, f = os.path.split(config.log)
    if not os.path.isdir(d):
        os.makedirs(d)

    response = requests.get(method_url('rtm.start'), params={'token': config.token})

    if response.status_code == 200:
        r = json.loads(response.text)
        ok = r.get('ok')
        if ok:
            websocket_url = r['url']
            user_id = r['self']['id']
            loop = asyncio.get_event_loop()
            loop.run_until_complete(listen(websocket_url, loop))

        else:
            print('Connection failed with error: {}'.format(r.get('error')))
    else:
        print(response.status_code)


EVENT_TYPES = {
    'hello': {'action': report},
    'message': {'action': handle_message},
    'user_typing': {'action': ignore},
    'channel_marked': {'action': report},
    'channel_created': {'action': report},
    'channel_joined': {'action': report},
    'channel_left': {'action': report},
    'channel_deleted': {'action': report},
    'channel_rename': {'action': report},
    'channel_archive': {'action': report},
    'channel_unarchive': {'action': report},
    'channel_history_changed': {'action': report},
    'im_created': {'action': report},
    'im_open': {'action': report},
    'im_close': {'action': report},
    'im_marked': {'action': report},
    'im_history_changed': {'action': report},
    'group_joined': {'action': report},
    'group_left': {'action': report},
    'group_open': {'action': report},
    'group_close': {'action': report},
    'group_archive': {'action': report},
    'group_unarchive': {'action': report},
    'group_rename': {'action': report},
    'group_marked': {'action': report},
    'group_history_changed': {'action': report},
    'file_created': {'action': archive},
    'file_shared': {'action': archive},
    'file_unshared': {'action': archive},
    'file_public': {'action': archive},
    'file_private': {'action': archive},
    'file_change': {'action': archive},
    'file_deleted': {'action': archive},
    'file_comment_added': {'action': archive},
    'file_comment_edited': {'action': archive},
    'file_comment_deleted': {'action': archive},
    'pin_added': {'action': report},
    'pin_removed': {'action': report},
    'presence_change': {'action': report},
    'manual_presence_change': {'action': report},
    'pref_change': {'action': report},
    'user_change': {'action': refresh},
    'team_join': {'action': refresh},
    'star_added': {'action': archive},
    'star_removed': {'action': archive},
    'reaction_added': {'action': archive},
    'reaction_removed': {'action': archive},
    'emoji_changed': {'action': ignore},
    'commands_changed': {'action': ignore},
    'team_plan_change': {'action': ignore},
    'team_pref_change': {'action': refresh},
    'team_rename': {'action': refresh},
    'team_domain_change': {'action': refresh},
    'email_domain_changed': {'action': refresh},
    'bot_added': {'action': refresh},
    'bot_changed': {'action': refresh},
    'accounts_changed': {'action': refresh},
    'team_migration_started': {'action': report},
    'subteam_created': {'action': archive},
    'subteam_updated': {'action': archive},
    'subteam_self_added': {'action': report},
    'subteam_self_removed': {'action': report},
    'pong': {'action': pong}
}


if __name__ == '__main__':
    main()