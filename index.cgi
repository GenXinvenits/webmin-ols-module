#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ui_print_header(undef, 'OpenLiteSpeed', '');

my $conf = "$config{'lsws'}/conf/httpd_config.conf";
my @vhosts;

if (open(my $fh, '<', $conf)) {
    while (my $line = <$fh>) {
        if ($line =~ /^\s*virtualhost\s+(\S+)\s*\{/) {
            push(@vhosts, $1);
        }
    }
    close($fh);
}

sub get_value {
    my ($content, $name) = @_;
    if ($content =~ /^\s*\Q$name\E\s+(.+?)\s*$/m) {
        my $value = $1;
        $value =~ s/\s+$//;
        return $value;
    }
    return '';
}

print "<h2>OpenLiteSpeed Virtual Hosts</h2>";
print "<p>Select a domain to manage its configuration and view its logs.</p>";

if (!@vhosts) {
    print "<p>No virtual hosts were found in:</p>";
    print "<pre>" . &html_escape($conf) . "</pre>";
}
else {
    print "<table class='list' width='100%'>";
    print "<tr>";
    print "<th>Virtual Host</th><th>Domain</th><th>Document Root</th>";
    print "<th>PHP</th><th>SSL</th><th>Rewrite</th><th>Status</th><th>Action</th>";
    print "</tr>";

    foreach my $vh (@vhosts) {
        my $root = "$config{'lsws'}/domains/$vh";
        my $vhconf = "$root/conf/vhconf.conf";
        my $conf_exists = -f $vhconf;
        my ($domain, $docroot, $php) = ('', '', '');
        my $ssl = 'No';
        my $rewrite = 'No';

        if ($conf_exists) {
            my $content = &read_file_contents($vhconf);
            $domain = get_value($content, 'vhDomain');
            $docroot = get_value($content, 'docRoot');
            $php = $1 if $content =~ /^\s*path\s+(\S+)\s*$/m;
            $ssl = 'Yes' if $content =~ /^\s*vhssl\s*\{/m;
            $rewrite = 'Yes' if $content =~ /^\s*rewrite\s*\{/m;
        }

        print "<tr>";
        print "<td><b>" . &html_escape($vh) . "</b></td>";
        print "<td>" . &html_escape($domain || '—') . "</td>";
        print "<td>" . &html_escape($docroot || '—') . "</td>";
        print "<td>" . &html_escape($php || '—') . "</td>";
        print "<td>" . ($ssl eq 'Yes' ? "<span style='color:green'><b>Yes</b></span>" : "<span style='color:#888'>No</span>") . "</td>";
        print "<td>" . ($rewrite eq 'Yes' ? "<span style='color:green'><b>Yes</b></span>" : "<span style='color:#888'>No</span>") . "</td>";

        if ($conf_exists) {
            print "<td><span style='color:green'><b>Ready</b></span></td>";
            print "<td>" . &ui_link("config.cgi?vh=" . &urlize($vh), "Manage") . "</td>";
        }
        else {
            print "<td><span style='color:red'><b>Not configured</b></span></td>";
            print "<td><span style='color:#888'>Unavailable</span></td>";
        }
        print "</tr>";
    }
    print "</table>";
}

print "<h2>Server</h2>";
print "<table class='list' width='100%'>";
print "<tr><td>" . &ui_link("listeners.cgi", "Listeners") . "</td></tr>";
print "<tr><td>" . &ui_link("service.cgi?action=restart", "Restart OpenLiteSpeed") . "</td></tr>";
print "</table>";

&ui_print_footer('', 'index.cgi');
