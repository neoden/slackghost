#!/usr/bin/env python

import sys
import os
import json
import ast
import pymongo


def main():
    db = pymongo.MongoClient().ghost

    with open(sys.argv[1]) as f:
        for line in f:
            obj = ast.literal_eval(line)
            if 'ts' in obj:
                obj['ts'] = float(obj['ts'])
            db.event_log.insert(obj)


if __name__ == '__main__':
    main()