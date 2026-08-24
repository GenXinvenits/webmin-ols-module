#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ui_print_header(undef, 'OpenLiteSpeed Logs', '');

&ReadParse();

my $log = $in{'log'} || 'error';
$log =~ s/[^A-Za-z0-9_-]//g;

my %logs = (
    error  => "$config{'lsws'}/logs/error.log",
    access => "$config{'lsws'}/logs/access.log",
);

if (!exists $logs{$log}) {
    $log = 'error';
}

my $file = $logs{$log};
my $lines_to_show = 200;
my @lines;
my $read_error = '';

if (open(my $fh, '<', $file)) {
    @lines = <$fh>;
    close($fh);

    if (@lines > $lines_to_show) {
        @lines = @lines[-$lines_to_show .. -1];
    }
}
else {
    $read_error = $!;
}

print "<h2>OpenLiteSpeed Logs</h2>";

print "<table class='formsection' width='100%'>";
print "<tr><td><b>Log</b></td><td>";

print "<a href='logs.cgi?log=error'>Error Log</a>";
print " &nbsp; | &nbsp; ";
print "<a href='logs.cgi?log=access'>Access Log</a>";

print "</td></tr>";

print "<tr><td><b>File</b></td><td><code>" .
      &html_escape($file) .
      "</code></td></tr>";

print "<tr><td><b>Showing</b></td><td>Last " .
      $lines_to_show .
      " lines</td></tr>";
print "</table>";

print "<br>";

if ($read_error) {
    print "<div class='error'>Unable to read log: " .
          &html_escape($read_error) .
          "</div>";
}
else {
    print "<textarea readonly style='width:100%;height:600px;" .
          "font-family:monospace;white-space:pre;'>";
    print &html_escape(join('', @lines));
    print "</textarea>";
}

print "<br><br>";
print "<a href='logs.cgi?log=" . &urlize($log) . "'>Refresh</a>";
print " &nbsp; ";
print "<a href='index.cgi'>Back to OpenLiteSpeed</a>";

&ui_print_footer("index.cgi");
