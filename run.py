#!/usr/bin/env python

import requests
import json
import time
import re
from pprint import pprint

import asyncio
import websockets


API_URL = 'https://slack.com/api/'
POLLING_INTERVAL = 0.1


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
        pprint(event)
        if event.get('type') == 'message':
            return self.handle_message(event)

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


@asyncio.coroutine
def listen(bot):
    websocket = yield from websockets.connect(bot.url)

    while True:
        event = yield from websocket.recv()
        r = bot.handle(json.loads(event))
        if r:
            yield from websocket.send(r)

        time.sleep(POLLING_INTERVAL)

    yield from websocket.close()


def main(token):
    response = requests.get(method_url('rtm.start'), params={'token': token})

    if response.status_code == 200:
        r = json.loads(response.text)
        ok = r.get('ok')
        if ok:
            websocket_url = r['url']
            bot = Bot(r)
            asyncio.get_event_loop().run_until_complete(listen(bot))
        else:
            print('Connection failed with error: {}'.format(r.get('error')))
    else:
        print(response.status_code)



if __name__ == '__main__':
    token = open('token.txt').read().strip()
    main(token)