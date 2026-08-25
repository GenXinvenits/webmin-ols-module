#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'SSL Certificate Manager', '');
&ReadParse();

# UI change: the existing Let's Encrypt renewal action is rendered inside the
# certificate form and is hidden unless the Let's Encrypt radio is selected.
# The renewal button is toggled by the same sync() function that controls the
# Let's Encrypt panel, so self-signed mode never shows the renewal action.

