#!/usr/bin/env python

import requests
import json
import time
import re
import signal
import functools
from pprint import pprint

import asyncio
import websockets


API_URL = 'https://slack.com/api/'


class Shutdown(Exception):
    pass


def method_url(name):
    return API_URL + name


class Bot():
    def __init__(self, data):
        try:
            self.url = data['url']
            self.id = data['self']['id']
            self.name = data['self']['name']
            print('I am {}. My ID is {}'.format(self.name, self.id))
        except KeyError as e:
            print('Bot initialization failed')
            raise e
        
    def handle(self, event):
        global pings

        pprint(event)
        event_type = event.get('type')
        if event_type == 'message':
            return self.handle_message(event)
        elif event_type == 'pong':
            print('pong')
            pings.pop(event.get('reply_to'))


    def handle_message(self, event):
        text = event.get('text')
        user = event.get('user')
        if text and user and re.search('<@{}>'.format(self.id), text):
            print('I was mentioned in a message')
            return json.dumps({
                'type': 'message',
                'channel': event['channel'],
                'text': 'привет <@{}>'.format(user)
            })

ping_handle = None
pings = {}

def ping(loop, websocket):
    global ping_handle
    global ping_id

    if len(pings) > 0:
        # опа, за 5 сек pong не вернулся
        print('alarm!')
    else:
        print('ping')
        ping_id = int(loop.time())
        pings[ping_id] = True

        msg = json.dumps({'id': ping_id, 'type': 'ping'})
        asyncio.ensure_future(websocket.send(msg))
        ping_handle = loop.call_later(5, ping, loop, websocket)



async def listen(bot, loop):
    global ping_handle

    websocket = await websockets.connect(bot.url)

    while True:
        ping_handle = loop.call_later(5, ping, loop, websocket)
        event = await websocket.recv()
        ping_handle.cancel()

        r = bot.handle(json.loads(event))
        if r:
            await websocket.send(r)

    await websocket.close()


def main(token):
    response = requests.get(method_url('rtm.start'), params={'token': token})

    if response.status_code == 200:
        r = json.loads(response.text)
        ok = r.get('ok')
        if ok:
            websocket_url = r['url']
            bot = Bot(r)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(listen(bot, loop))

        else:
            print('Connection failed with error: {}'.format(r.get('error')))
    else:
        print(response.status_code)



if __name__ == '__main__':
    token = open('token.txt').read().strip()
    main(token)