#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ui_print_header(undef, 'OpenLiteSpeed Listeners', '');

my $conf = "$config{'lsws'}/conf/httpd_config.conf";
my @listeners;
my $current;

if (open(my $fh, '<', $conf)) {
    while (my $line = <$fh>) {
        if ($line =~ /^\s*listener\s+(\S+)\s*\{/) {
            $current = {
                name => $1,
                address => '',
                secure => 0,
                maps => [],
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
                push(@{$current->{maps}}, { vh => $1, domains => $2 });
                next;
            }
        }

        if ($current && $line =~ /^\s*\}/) {
            $current = undef;
        }
    }
    close($fh);
}

print <<'HTML';
<style>
.ols-listeners { max-width:1200px; margin:0 auto; }
.ols-listener-hero { padding:22px 24px; margin:0 0 20px; border-radius:10px; border:1px solid var(--border-color,rgba(128,128,128,.25)); }
.ols-listener-hero-top { display:flex; align-items:center; justify-content:space-between; gap:20px; }
.ols-listener-hero h1 { margin:0 0 5px; font-size:26px; }
.ols-listener-hero p { margin:0; opacity:.68; font-size:13px; }
.ols-listener-count { padding:7px 11px; border-radius:999px; background:rgba(128,128,128,.12); font-size:11px; font-weight:700; white-space:nowrap; }
.ols-listener-list { display:grid; gap:12px; }
.ols-listener-card { border:1px solid var(--border-color,rgba(128,128,128,.25)); border-radius:10px; overflow:hidden; }
.ols-listener-card-head { display:flex; align-items:center; justify-content:space-between; gap:15px; padding:16px 18px; border-bottom:1px solid var(--border-color,rgba(128,128,128,.18)); }
.ols-listener-name { font-size:16px; font-weight:700; }
.ols-listener-address { margin-top:3px; font-size:12px; opacity:.65; }
.ols-protocol { padding:4px 9px; border-radius:999px; font-size:10px; font-weight:700; }
.ols-protocol-http { background:rgba(128,128,128,.13); }
.ols-protocol-https { background:rgba(40,167,69,.13); color:#43b56b; }
.ols-listener-body { display:grid; grid-template-columns:1fr 1fr; gap:0; }
.ols-listener-stat { padding:14px 18px; border-right:1px solid var(--border-color,rgba(128,128,128,.15)); }
.ols-listener-stat:last-child { border-right:0; }
.ols-stat-label { margin-bottom:4px; font-size:10px; text-transform:uppercase; letter-spacing:.05em; opacity:.55; }
.ols-stat-value { font-size:13px; font-weight:600; }
.ols-listener-foot { display:flex; justify-content:space-between; align-items:center; gap:15px; padding:11px 18px; border-top:1px solid var(--border-color,rgba(128,128,128,.15)); }
.ols-listener-maps { font-size:11px; opacity:.62; }
.ols-edit { text-decoration:none; font-weight:600; }
.ols-back { display:inline-block; margin-top:18px; text-decoration:none; }
.ols-empty { padding:24px; border:1px solid var(--border-color,rgba(128,128,128,.25)); border-radius:10px; opacity:.7; }
@media(max-width:650px) { .ols-listener-hero-top { align-items:flex-start; flex-direction:column; } .ols-listener-body { grid-template-columns:1fr; } .ols-listener-stat { border-right:0; border-bottom:1px solid var(--border-color,rgba(128,128,128,.15)); } .ols-listener-stat:last-child { border-bottom:0; } }
</style>
HTML

print "<div class='ols-listeners'>";
print "<div class='ols-listener-hero'>";
print "<div class='ols-listener-hero-top'>";
print "<div><h1>Listeners</h1><p>Global HTTP and HTTPS endpoints for OpenLiteSpeed.</p></div>";
print "<div class='ols-listener-count'>" . scalar(@listeners) . " listener" . (scalar(@listeners) == 1 ? '' : 's') . "</div>";
print "</div></div>";

if (!@listeners) {
    print "<div class='ols-empty'>No listeners were found in <code>" . &html_escape($conf) . "</code>.</div>";
}
else {
    print "<div class='ols-listener-list'>";
    foreach my $listener (@listeners) {
        my $https = $listener->{secure} ? 1 : 0;
        my $protocol = $https ? 'HTTPS' : 'HTTP';
        my $maps = scalar @{$listener->{maps}};

        print "<div class='ols-listener-card'>";
        print "<div class='ols-listener-card-head'>";
        print "<div><div class='ols-listener-name'>" . &html_escape($listener->{name}) . "</div>";
        print "<div class='ols-listener-address'><code>" . &html_escape($listener->{address}) . "</code></div></div>";
        print "<span class='ols-protocol " . ($https ? 'ols-protocol-https' : 'ols-protocol-http') . "'>$protocol</span>";
        print "</div>";

        print "<div class='ols-listener-body'>";
        print "<div class='ols-listener-stat'><div class='ols-stat-label'>Address</div><div class='ols-stat-value'><code>" . &html_escape($listener->{address}) . "</code></div></div>";
        print "<div class='ols-listener-stat'><div class='ols-stat-label'>Virtual Hosts</div><div class='ols-stat-value'>$maps mapped virtual host" . ($maps == 1 ? '' : 's') . "</div></div>";
        print "</div>";

        print "<div class='ols-listener-foot'>";
        print "<span class='ols-listener-maps'>Global listener · " . ($https ? 'TLS enabled' : 'Plain HTTP') . "</span>";
        print &ui_link("listener.cgi?listener=" . &urlize($listener->{name}), "Edit listener →");
        print "</div>";
        print "</div>";
    }
    print "</div>";
}

print "<a class='ols-back' href='index.cgi'>← Back to OpenLiteSpeed</a>";
print "</div>";

&ui_print_footer('index.cgi');
