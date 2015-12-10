#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of Keepass-Webdav-Git synchro stuff.
#
#
# Software is free software released under the "Modified BSD license"
#
# Copyright (c) 2015-2015 Psychedelys
#

import configparser
import os
import sys
from flask import Flask, request, make_response, send_file, Response, abort
from werkzeug import secure_filename
from logbook import debug, info, warn, error
import pprint
from functools import wraps
import urllib
import re
import logging
import base64

from dulwich.repo import Repo


app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
runPath = os.path.dirname(os.path.realpath(__file__))
cfg_file = runPath + '/../etc/configuration.ini'


def read_config():
    """ Set configuration file data into local dictionnary. """
    config = configparser.ConfigParser()
    try:
        config.read_file(open(cfg_file))
    except OSError as e:
        error("can't read configuration file %s. %s." % (cfg_file, str(e)))

    # Check if all keys are in the file
    keys = ['MediaRoot', 'Port', 'Debug', 'Root_URL', 'realhost', 'Committer']
    for key in keys:
        if key not in config['webdavgit']:
            error("config file %s incomplete, please check!" % (cfg_file))
    return config['webdavgit']


def end(code, message):
    error(message)
    abort(code, message)


pp = pprint.PrettyPrinter(indent=4)
config = read_config()

allowed_extention = ['.kdbx', '.kdbx.tmp']
root_url = config['Root_URL']
Debug = config['Debug']
realhost = config['realhost']
basepath = os.path.join(config['MediaRoot'])


def __withException(func):
    @wraps(func)
    def wrapper(path):
        try:
            path = re.sub(r'^'+root_url, '', path)
            path = urllib.parse.unquote(path, encoding='utf-8')
            return func(path)
        except FileNotFoundError:
            return '', 404
        except PermissionError:
            return '', 403
    return wrapper


# Max must be the same as the nginx parameter client_max_body_size
# if nginx is used in front
app.config['MAX_CONTENT_LENGTH'] = 3 * 1024 * 1024


@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options(path):
    response = make_response()
    response.headers['Allow'] =\
        'GET, DELETE, MOVE, PUT'
    response.headers['DAV'] = '1'
    return response


@app.route('/', defaults={'path': ''}, methods=['MOVE'])
@app.route('/<path:path>', methods=['MOVE'])
@__withException
def move(path):
    debug("MOVE with path '%s'" % (path))

    try:
        filename = secure_filename(path)
    except Exception as e:
        debug("secure_filename failed: %s:%s" % (path, str(e)))

    debug("ok: secure_filename succeed %s" % filename)
    # Prevent uploading file with more than 1 dot.
    dotCount = filename.count('.')
    if dotCount != 2:
        error("file do not contains 2 dot.")
        end(403, "file not contains 2 dot!")

    debug("ok: file contains just 2 dot.")

    root, ext = os.path.splitext(filename)
    first_ext = os.path.splitext(root)[1].lower()
    extension = first_ext + ext
    extension = extension.lower()
    if extension not in allowed_extention:
        error("file extension NOT allowed '%s'." % extension)
        debug("error: allowed %s." % (pp.pformat(allowed_extention)))
        end(403, "file extension not allowed!")

    debug("ok: file extension allowed.")

    basepath = os.path.join(config['MediaRoot'])
    filepath = os.path.join(basepath, filename)
    if not os.path.isdir(basepath):
        debug("error: Folder do not exist %s" % str(basepath))
        end(403, "oups, Folder do not exist '%s'." % (str(basepath)))

    if not os.path.isfile(filepath):
        debug("error: Folder do not exist %s" % str(filepath))
        end(403, "oups, Folder do not exist '%s'." % (str(filepath)))

    dest = request.headers.get('Destination')
    dest = re.sub(r'^https?://'+realhost+'/'+root_url, '', dest)
    dest = urllib.parse.unquote(dest, encoding='utf-8')

    try:
        destfilename = secure_filename(dest)
    except Exception as e:
        debug("secure_filename failed: %s:%s" % (dest, str(e)))

    debug("ok: secure_filename succeed %s" % destfilename)
    # Prevent uploading file with more than 1 dot.
    dotCount = destfilename.count('.')
    if dotCount != 1:
        error("destfile do contains 1 dot.")
        end(403, "destfile contains 1 dot!")

    debug("ok: destfile contains just 1 dot.")

    extension = os.path.splitext(destfilename)[1].lower()
    if extension not in allowed_extention:
        error("desfile extension NOT allowed '%s'." % extension)
        debug("error: allowed %s." % (pp.pformat(allowed_extention)))
        end(403, "destfile extension not allowed!")

    destfilepath = os.path.join(basepath, destfilename)
    if os.path.isfile(destfilepath):
        debug("File '%s' exist on system." % (destfilepath))
        end(404, "File exist")

    try:
        os.rename(filepath, destfilepath)
    except FileExistsError:
        debug("Could not move file from '%s' to '%s' on system." % (filepath, destfilepath))
        end(403, "Could not move file.")
    except Exception as e:
        debug("error: %s" % str(e))
        debug("Could not move file from '%s' to '%s' on system." % (filepath, destfilepath))
        end(403, "Could not move file.")

    # The interresting stuff now, we take a Git image.
    gitbasepath = os.path.join(basepath, '.git')
    if not os.path.isdir(gitbasepath):
        debug("error: Folder do not exist %s" % str(gitbasepath))
        try:
            repo = Repo.init(basepath, mkdir=False)
        except Exception as e:
            debug("Git repo creation failed:%s:%s" % (basepath, str(e)))
    GIT_REPOSITORY = Repo(basepath)

    try:
        if 'Authorization' in request.headers:
            # "Authorization: Basic BASE64"
            real_committer = request.headers.get('Authorization')
            real_committer = base64.b64decode(real_committer.split(' ')[1]).decode('utf-8').split(':', 1)[0]
            real_committer = urllib.parse.unquote(real_committer, encoding='utf-8')
            real_firstname = real_committer.split('@', 1)[0]
            real_name = real_committer.split('@', 1)[1].split('.', 1)[0]
            real_committer = real_firstname.title() + ' ' + real_name.title() + ' <' + real_committer + '>'
            debug("ok: real_committer:%s" % (real_committer))

    except Exception as e:
        debug("Git commiter fetch: failed:%s" % (str(e)))

    if not real_committer:
        real_committer = config("Committer")
        debug("ok: fake_committer:%s" % (real_committer))

    try:
        GIT_REPOSITORY.stage([destfilename])
        GIT_REPOSITORY.do_commit(basepath, committer=real_committer)
    except Exception as e:
        debug("Git repo commit failed:%s" % (str(e)))

    return '', 204


@app.route('/', defaults={'path': ''}, methods=['GET'])
@app.route('/<path:path>', methods=['GET'])
@__withException
def get(path):
    # remove anypath inside the filename to insure against injection.
    # ex: upfil.raw_filename should not contain any '..'
    # already done by secure_filename
    # filename = os.path.basename(filename)

    # TODO, check if path is allowed
    debug("GET with path '%s'" % (path))
    try:
        path = re.sub(r'^'+root_url, '', path)
        path = urllib.parse.unquote(path, encoding='utf-8')
    except Exception as e:
        debug("path regex failed:%s:%s" % (path, str(e)))

    debug("get path '%s'" % (path))

    try:
        filename = secure_filename(path)
    except Exception as e:
        debug("secure_filename failed: %s:%s" % (path, str(e)))

    debug("ok: secure_filename succeed %s" % filename)
    # Prevent uploading file with more than 1 dot.
    dotCount = filename.count('.')
    if dotCount != 1:
        error("file do contains more than 1 dot.")
        end(403, "file contains more than 1 dot!")

    debug("ok: file do not contains more than 1 dot.")
    # Prevent uploading from unwanted file which can be used for injection
    extension = os.path.splitext(filename)[1].lower()
    if extension not in allowed_extention:
        error("file extension NOT allowed '%s'." % extension)
        debug("error: allowed %s." % (pp.pformat(allowed_extention)))
        end(403, "file extension not allowed!")

    debug("ok: file extension allowed.")

    basepath = os.path.join(config['MediaRoot'])
    filepath = os.path.join(basepath, filename)
    if not os.path.isdir(basepath):
        debug("error: Folder do not exist %s" % str(basepath))
        end(404, "oups, Folder do not exist '%s'." % (str(basepath)))

    if not os.path.isfile(filepath):
        debug("error: Folder do not exist %s" % str(filepath))
        end(404, "oups, Folder do not exist '%s'." % (str(filepath)))

    return send_file(filepath, mimetype='application/octet-stream')


@app.route('/', defaults={'path': ''}, methods=['PUT'])
@app.route('/<path:path>', methods=['PUT'])
@__withException
def put(path):
    debug("PUT with path '%s'" % (path))

    # remove anypath inside the filename to insure against injection.
    # ex: upfil.raw_filename should not contain any '..'
    # already done by secure_filename
    # filename = os.path.basename(filename)
    try:
        filename = secure_filename(path)
    except Exception as e:
        debug("secure_filename failed: %s:%s" % (path, str(e)))

    debug("ok: secure_filename succeed %s" % filename)
    # Prevent uploading file with more than 1 dot.
    dotCount = filename.count('.')
    if dotCount != 2:
        error("file do not contains more than 2 dot.")
        end(403, "file do not contains 2 dot!")

    debug("ok: file contains just 2 dot.")
    # Prevent uploading from unwanted file which can be used for injection
    root, ext = os.path.splitext(filename)
    first_ext = os.path.splitext(root)[1].lower()
    extension = first_ext + ext
    extension = extension.lower()
    if extension not in allowed_extention:
        error("file extension NOT allowed '%s'." % extension)
        debug("error: allowed %s." % (pp.pformat(allowed_extention)))
        end(403, "file extension not allowed!")

    debug("ok: file extension '%s' allowed." % (extension))

    basepath = os.path.join(config['MediaRoot'])
    filepath = os.path.join(basepath, filename)
    if not os.path.isdir(basepath):
        debug("Need to create folder '%s' on system." % (basepath))
        try:
            os.makedirs(basepath)
        except Exception as e:
            debug("error: Cannot create folder %s" % str(e))
            end(400, "oups, cannot create directory '%s'." % (str(e)))

    if not os.path.isfile(filepath):
        debug("Storing file %s on system." % (filepath))
        filesize = -1
        try:
            filesize = int(request.headers.get('Content-Length'))
        except TypeError as e:
            debug("error: %s" % str(e))
            end(400, "missing file size in the request!")
        except Exception as e:
            debug("error: %s" % str(e))
            end(400, "missing file size in the request!")

        upfile = request.data

        # save file
        debug("upfile path: '%s'." % (filepath))
        with open(filepath, "wb") as fo:
            fo.write(upfile)

        # check file size in request against written file size
        if filesize != os.stat(filepath).st_size:
            debug("error: file sizes do not match '%s' <> '%s'." % (filesize, os.stat(filepath).st_size))
            end(411, "file sizes do not match!")

        return ('', 201)

    else:
        warn("file " + filepath + " already exists")
        end(400, "file already exist!")


@app.route('/', defaults={'path': ''}, methods=['DELETE'])
@app.route('/<path:path>', methods=['DELETE'])
@__withException
def delete(path):
    debug("DELETE with path '%s'" % (path))

    try:
        filename = secure_filename(path)
    except Exception as e:
        debug("secure_filename failed: %s:%s" % (path, str(e)))

    debug("ok: secure_filename succeed %s" % filename)
    # Prevent uploading file with more than 1 dot.
    dotCount = filename.count('.')
    if dotCount > 2 and dotCount < 1:
        error("file do contains less than 1 dot or more than 2 dot.")
        end(403, "file contains less than 1 dot or more than 2 dot!")

    debug("ok: file contains just 1 or 2 dot.")

    if dotCount == 1:
        extension = os.path.splitext(filename)[1].lower()
    elif dotCount == 2:
        root, ext = os.path.splitext(filename)
        first_ext = os.path.splitext(root)[1].lower()
        extension = first_ext + ext
        extension = extension.lower()
    if extension not in allowed_extention:
        error("file extension NOT allowed '%s'." % extension)
        debug("error: allowed %s." % (pp.pformat(allowed_extention)))
        end(403, "file extension not allowed!")

    basepath = os.path.join(config['MediaRoot'])
    filepath = os.path.join(basepath, filename)
    if not os.path.isdir(basepath):
        debug("Path '%s' do not exist." % (basepath))
        end(404, "Path do not exist.")

    if not os.path.isfile(filepath):
        debug("File '%s' do not exist on system." % (filepath))
        end(404, "File do not exist")

    try:
        os.unlink(filepath)
    except Exception as e:
        debug("error: %s" % str(e))
        debug("Could not delete file '%s' on system." % (filepath))
        end(403, "missing file size in the request!")

    return '', 204


if __name__ == '__main__':
    app.debug = Debug
    flaskHost = '127.0.0.1'
    flaskPort = int(config['Port'])
    flaskDebug = Debug
    app.run(host=flaskHost, port=flaskPort, debug=flaskDebug, threaded=True)
