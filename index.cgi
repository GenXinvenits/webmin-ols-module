#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ui_print_header(undef, 'OpenLiteSpeed', '');

my $status  = &service_status();
my $version = &ols_version();

print "<h2>OpenLiteSpeed Server</h2>";

print "<table class=\"formsection\" width=\"100%\">";

print "<tr>";
print "<td><b>Status</b></td>";
print "<td>$status</td>";
print "</tr>";

print "<tr>";
print "<td><b>Version</b></td>";
print "<td>" . &html_escape($version) . "</td>";
print "</tr>";

print "<tr>";
print "<td><b>Installation</b></td>";
print "<td>" . &html_escape($config{'lsws'}) . "</td>";
print "</tr>";

print "<tr>";
print "<td><b>Configuration</b></td>";
print "<td>" . &html_escape($config{'config'}) . "</td>";
print "</tr>";

print "<tr>";
print "<td><b>Service</b></td>";
print "<td>" . &html_escape($config{'service'}) . "</td>";
print "</tr>";

print "</table>";

print "<h2>Service Control</h2>";

print "<div class=\"ui_buttons\">";
print &ui_link_button("service.cgi?action=start", "Start OpenLiteSpeed");
print " ";
print &ui_link_button("service.cgi?action=stop", "Stop OpenLiteSpeed");
print " ";
print &ui_link_button("service.cgi?action=restart", "Restart OpenLiteSpeed");
print "</div>";

print "<h2>Management</h2>";

print "<table class=\"list\" width=\"100%\">";

print "<tr>";
print "<td><a href=\"config.cgi\">Configuration</a></td>";
print "</tr>";

print "<tr>";
print "<td><a href=\"vhosts.cgi\">Virtual Hosts</a></td>";
print "</tr>";

print "<tr>";
print "<td><a href=\"listeners.cgi\">Listeners</a></td>";
print "</tr>";

print "<tr>";
print "<td><a href=\"logs.cgi\">Logs</a></td>";
print "</tr>";

print "</table>";

&ui_print_footer("", "index.cgi");
