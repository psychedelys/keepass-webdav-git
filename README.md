# keepass-webdav-git
python minimal webdav support with keepass auto-versionning.

The following minimal flask server is only planned to have a [KeePass](http://keepass.info/) sync working with WebDAV -the default one-. At the end of the synchronisation, the new uploaded keepass is automatically commited in the local git directory.

# This is a prototype working.
each sync is creating a new git version, even if nothing changed.

# Keepass triggers
Defined  trigger for opening and saving your KeePass. Thus the update will be automatic, at opening/saving.
[Triggers exemple](./KeePass_triggers.xml): SyncOnOpen/SyncOnSave 

# Dependancy
[dulwich](https://github.com/eberle1080/dulwich-py3k.git): a fully pythonized Git lib. 

# Caution:
Authentication is not done inside, just doing it now with a _auth in nginx.
* https://github.com/nginxinc/nginx-ldap-auth.git

# PEP8 Compliance
Code should be PEP8 compliant.

# TODO:
* add pip for quicker deployment.
* add full dependancy.
* add more docs.
* add git sub for dulwich
* add a better flask login with flask.external.login
