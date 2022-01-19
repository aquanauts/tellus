# Tellus
Tellus is a central hub for connecting various information

Tellus' basic unit of information is a Tell. Tells have a bunch of info including tags, which are used to tie different Tells together.

The current sources of information within Tellus are listed below.

## Go
Tellus' primary function is to allow us to define short, human-readable aliases for useful URLs within Aqauatic.

## User (aka 'Be')
Tellus has a pseudo-login that will let you "Become" a user (ideally, yourself).  Right now this is just used for audit info but Tellus will do more with this eventually.

Note that it is piggybacking off of github users for valid user names for now.

## Other Data Sources
Tellus draws from a number of different data sources to populate itself and tie things together.

### Github - tellus.yml files
If you put a [tellus.yml](https://github.com/aquanauts/tellus/blob/master/tellus.yml) file into Github, Tellus will automatically grab it and attempt to create or update Tells within Tellus based on the information inside.  The only required attribute is 'alias'.

The first item in the tellus.yml is considered the "primary" Tell, and other Tells can be related to that one.

Note: you can also add arbitrary attributes to these files and Tellus will put them into an 'Additional Data' block (see below).

## Tells

Tells consist of the following information:

- `alias` (*required and **opinionated** *): the key of the Tell.
	* Aliases *must be* all lowercase, separated by dashes.  Tellus will largely try to convert an alias to this format.
	* At present, Aliases are immutable.
- `go-url`: the url for the Tell, to which Go will redirect.
	* This is not required.
	* In certain cases, this will be automatically generated
- `description`: additional human-readable information about the Tell.
- `tags`:  a set of identifying tags for the Tell.  These affect display and link Tells together in various locations within Tellus.
- `category` (read-only): Tellus' internal categories for the Tell (used for certain behaviors).

### Additional Data

Tells coming from other sources will sometimes have additional information attached to them.   Tellus will attempt to store and display those values as best it can on the Tell.
