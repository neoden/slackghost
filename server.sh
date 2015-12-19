#!/bin/bash

VENVDIR=/opt/venv/slack
BINDIR=/srv/ghost

cd $BINDIR
source $VENVDIR/bin/activate
$BINDIR/webserver.py