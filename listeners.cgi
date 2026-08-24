#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ui_print_header(undef, 'OpenLiteSpeed Listeners', '');

my $conf = "$config{'lsws'}/conf/httpd_config.conf";

my @listeners;
my $current = '';

if (open(my $fh, '<', $conf)) {

    while (my $line = <$fh>) {

        if ($line =~ /^\s*listener\s+(\S+)\s*\{/) {

            $current = {
                name    => $1,
                address => '',
                secure  => 0,
                maps    => [],
            };

            push(@listeners, $current);
            next;
        }

        if ($current) {

            if ($line =~ /^\s*address\s+(.+?)\s*$/) {
                $current->{address} = $1;
                next;
            }

            if ($line =~ /^\s*secure\s+(\d+)\s*$/) {
                $current->{secure} = $1;
                next;
            }

            if ($line =~ /^\s*map\s+(\S+)\s+(.+?)\s*$/) {
                push(
                    @{$current->{maps}},
                    {
                        vh      => $1,
                        domains => $2,
                    }
                );
                next;
            }
        }

        if ($current && $line =~ /^\s*\}/) {
            $current = '';
        }
    }

    close($fh);
}

print "<h2>OpenLiteSpeed Listeners</h2>";

if (!@listeners) {

    print "<p>No listeners were found in:</p>";
    print "<pre>" . &html_escape($conf) . "</pre>";

}
else {

    print "<table class='list' width='100%'>";

    print "<tr>";
    print "<th>Listener</th>";
    print "<th>Address</th>";
    print "<th>Protocol</th>";
    print "<th>Virtual Hosts</th>";
    print "<th>Action</th>";
    print "</tr>";

    foreach my $listener (@listeners) {

        my $protocol =
            $listener->{secure}
            ? '<span style="color:green"><b>HTTPS</b></span>'
            : '<span style="color:#555"><b>HTTP</b></span>';

        my $maps = scalar @{$listener->{maps}};

        print "<tr>";

        print "<td><b>" .
              &html_escape($listener->{name}) .
              "</b></td>";

        print "<td><code>" .
              &html_escape($listener->{address}) .
              "</code></td>";

        print "<td>$protocol</td>";

        print "<td>" .
              $maps .
              "</td>";

        print "<td>" .
              &ui_link(
                  "listener.cgi?listener=" .
                  &urlize($listener->{name}),
                  "Edit"
              ) .
              "</td>";

        print "</tr>";
    }

    print "</table>";
}

print "<br>";

print "<a href='index.cgi'>Back to OpenLiteSpeed</a>";

&ui_print_footer("index.cgi");
