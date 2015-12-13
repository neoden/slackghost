#!/usr/bin/env python

import requests
import json
from pprint import pprint

import asyncio
import websockets


API_URL = 'https://slack.com/api/'


def method_url(name):
	return API_URL + name


@asyncio.coroutine
def listen(url):
	websocket = yield from websockets.connect(url)
	event = yield from websocket.recv()
	pprint(event)
	yield from websocket.close()


def main(token):
	response = requests.get(method_url('rtm.start'), params={'token': token})

	if response.status_code == 200:
		r = json.loads(response.text)
		ok = r['ok']
		if ok:
			websocket_url = r['url']
			asyncio.get_event_loop().run_until_complete(listen(websocket_url))
		else:
			print('Connection failed')
	else:
		print(response.status_code)


if __name__ == '__main__':
	token = open('token.txt').read().strip()
	main(token)