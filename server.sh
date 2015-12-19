#!/bin/bash

VENVDIR=/srv/venv/slack
BINDIR=/srv/ghost

cd $BINDIR
source $VENVDIR/bin/activate
$BINDIR/webserver.py