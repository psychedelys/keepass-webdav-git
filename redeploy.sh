#!/bin/sh

MEDIA_ROOT=`grep mediaroot etc/configuration.ini | awk -F= '{ print $2 }'`
APP='keepasswebdavgit'

cd ${MEDIA_ROOT}
/etc/init.d/uwsgi stop ${APP}
find . -type f -iname "*.pyc" -delete
find . -type d -name '__pycache__'  -delete
/etc/init.d/uwsgi restart ${APP}
echo "tail -f  /var/log/uwsgi/app/${APP}.log"
