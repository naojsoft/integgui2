IntegGUI2
=========

ABOUT
-----
This is the IntegGUI2 observation command GUI for Subaru Telescope.

USAGE
-----
  $ integgui2 --loglevel=20 --log=path/to/integgui2.log

add --stderr if you want to see logging output to the terminal as well.

REQUIRED PACKAGES
-----------------

- pygobject
- pycairo
- ginga
- g2cam
- g2client

Packages that will be installed by the installer if not already
installed:

- pyyaml

INSTALLATION
------------

Install all prerequisites, then:

  $ pip install .

AUTHORS
-------
T. Inagaki
R. Kackley
E. Jeschke


