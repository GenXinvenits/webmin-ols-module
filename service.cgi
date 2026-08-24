#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ReadParse();

&ui_print_header(undef, 'OpenLiteSpeed Service', '');

my $action = $in{'action'} || '';

if ($action !~ /^(start|stop|restart)$/) {
    print "<h2>OpenLiteSpeed Service</h2>";
    print "<p><b>Invalid service action.</b></p>";
    print &ui_link_button("index.cgi", "Back to OpenLiteSpeed");
    &ui_print_footer("index.cgi");ui_print_footer("", "index.cgi");
    exit;
}

my $cmd = "/usr/bin/systemctl $action " .
          quotemeta($config{'service'}) . " 2>&1";

my $output = &backquote_command($cmd);
my $exit = $? >> 8;

print "<h2>OpenLiteSpeed Service</h2>";

if ($exit == 0) {
    print "<div class='success'>";
    print "<b>Service successfully $action" .
          ($action eq 'restart' ? "ed" :
           $action eq 'start'   ? "ed" :
                                  "ped") .
          ".</b>";
    print "</div>";
}
else {
    print "<div class='error'>";
    print "<b>Failed to $action OpenLiteSpeed service.</b>";
    print "</div>";

    if ($output) {
        print "<pre>";
        print &html_escape($output);
        print "</pre>";
    }
}

print "<br>";

my $status = &service_status();

print "<table class='formsection' width='100%'>";
print "<tr>";
print "<td><b>Current Status</b></td>";
print "<td>$status</td>";
print "</tr>";
print "</table>";

print "<br>";

print &ui_link_button("index.cgi", "Back to OpenLiteSpeed");

&ui_print_footer("index.cgi");ui_print_footer("", "index.cgi");
