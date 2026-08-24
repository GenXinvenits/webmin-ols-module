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
                name => $1, address => '', secure => 0,
                keyfile => '', certfile => '', maps => [],
            };
            push(@listeners, $current);
            next;
        }
        if ($current) {
            if ($line =~ /^\s*address\s+(.+?)\s*$/) { $current->{address} = $1; next; }
            if ($line =~ /^\s*secure\s+(\d+)\s*$/) { $current->{secure} = $1; next; }
            if ($line =~ /^\s*keyFile\s+(.+?)\s*$/) { $current->{keyfile} = $1; next; }
            if ($line =~ /^\s*certFile\s+(.+?)\s*$/) { $current->{certfile} = $1; next; }
            if ($line =~ /^\s*map\s+(\S+)\s+(.+?)\s*$/) {
                push(@{$current->{maps}}, { vh => $1, domains => $2 });
                next;
            }
        }
        if ($current && $line =~ /^\s*\}/) { $current = undef; }
    }
    close($fh);
}

print <<'HTML';
<style>
.ols-listeners{max-width:1200px;margin:0 auto}
.ols-listener-hero{padding:24px;margin:0 0 22px;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:12px}
.ols-listener-hero-top{display:flex;align-items:center;justify-content:space-between;gap:20px}
.ols-listener-hero h1{margin:0 0 5px;font-size:26px}.ols-listener-hero p{margin:0;opacity:.68;font-size:13px}
.ols-listener-count{padding:7px 11px;border-radius:999px;background:rgba(128,128,128,.12);font-size:11px;font-weight:700;white-space:nowrap}
.ols-listener-list{display:grid;gap:16px}
.ols-listener-card{border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:12px;overflow:hidden}
.ols-listener-card-head{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.18))}
.ols-listener-name{font-size:18px;font-weight:700}.ols-listener-address{margin-top:5px;font-size:13px;opacity:.65}
.ols-protocol{padding:5px 10px;border-radius:999px;font-size:10px;font-weight:700}.ols-protocol-http{background:rgba(128,128,128,.13)}.ols-protocol-https{background:rgba(40,167,69,.13);color:#43b56b}
.ols-listener-grid{display:grid;grid-template-columns:repeat(3,1fr)}
.ols-listener-stat{padding:17px 20px;border-right:1px solid var(--border-color,rgba(128,128,128,.15))}.ols-listener-stat:last-child{border-right:0}
.ols-stat-label{margin-bottom:6px;font-size:10px;text-transform:uppercase;letter-spacing:.06em;opacity:.52}.ols-stat-value{font-size:13px;font-weight:600;overflow-wrap:anywhere}
.ols-listener-cert{padding:15px 20px;border-top:1px solid var(--border-color,rgba(128,128,128,.15));font-size:11px}
.ols-listener-cert-row{display:flex;gap:12px;margin:4px 0}.ols-cert-label{min-width:72px;opacity:.52}.ols-cert-value{overflow-wrap:anywhere;opacity:.8}
.ols-listener-foot{display:flex;justify-content:space-between;align-items:center;gap:15px;padding:12px 20px;border-top:1px solid var(--border-color,rgba(128,128,128,.15))}
.ols-listener-maps{font-size:11px;opacity:.62}.ols-edit{text-decoration:none;font-weight:600}.ols-back{display:inline-block;margin-top:20px;text-decoration:none}
.ols-empty{padding:24px;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:12px;opacity:.7}
@media(max-width:700px){.ols-listener-hero-top{align-items:flex-start;flex-direction:column}.ols-listener-grid{grid-template-columns:1fr}.ols-listener-stat{border-right:0;border-bottom:1px solid var(--border-color,rgba(128,128,128,.15))}.ols-listener-stat:last-child{border-bottom:0}.ols-listener-cert-row{display:block}.ols-cert-label{display:block;margin-bottom:3px}}
</style>
HTML

print "<div class='ols-listeners'>";
print "<div class='ols-listener-hero'><div class='ols-listener-hero-top'>";
print "<div><h1>Listeners</h1><p>Global network endpoints used by OpenLiteSpeed to accept web traffic.</p></div>";
print "<div class='ols-listener-count'>" . scalar(@listeners) . " listener" . (scalar(@listeners)==1?'':'s') . "</div>";
print "</div></div>";

if (!@listeners) {
    print "<div class='ols-empty'>No listeners were found in <code>" . &html_escape($conf) . "</code>.</div>";
} else {
    print "<div class='ols-listener-list'>";
    foreach my $l (@listeners) {
        my $https=$l->{secure}?1:0;
        my $protocol=$https?'HTTPS':'HTTP';
        my $maps=scalar @{$l->{maps}};
        print "<div class='ols-listener-card'>";
        print "<div class='ols-listener-card-head'><div><div class='ols-listener-name'>" . &html_escape($l->{name}) . "</div><div class='ols-listener-address'><code>" . &html_escape($l->{address}) . "</code></div></div>";
        print "<span class='ols-protocol " . ($https?'ols-protocol-https':'ols-protocol-http') . "'>$protocol</span></div>";
        print "<div class='ols-listener-grid'>";
        print "<div class='ols-listener-stat'><div class='ols-stat-label'>Protocol</div><div class='ols-stat-value'>$protocol</div></div>";
        print "<div class='ols-listener-stat'><div class='ols-stat-label'>Virtual Hosts</div><div class='ols-stat-value'>$maps mapped virtual host" . ($maps==1?'':'s') . "</div></div>";
        print "<div class='ols-listener-stat'><div class='ols-stat-label'>Mode</div><div class='ols-stat-value'>" . ($https?'TLS / Secure':'Plain HTTP') . "</div></div>";
        print "</div>";
        if ($https) {
            print "<div class='ols-listener-cert'>";
            print "<div class='ols-listener-cert-row'><span class='ols-cert-label'>Certificate</span><code class='ols-cert-value'>" . &html_escape($l->{certfile}) . "</code></div>";
            print "<div class='ols-listener-cert-row'><span class='ols-cert-label'>Private key</span><code class='ols-cert-value'>" . &html_escape($l->{keyfile}) . "</code></div>";
            print "</div>";
        }
        print "<div class='ols-listener-foot'><span class='ols-listener-maps'>Global listener · " . ($https?'HTTPS endpoint':'HTTP endpoint') . "</span>";
        print &ui_link("listener.cgi?listener=" . &urlize($l->{name}), "Edit listener →");
        print "</div></div>";
    }
    print "</div>";
}
print "<a class='ols-back' href='index.cgi'>← Back to OpenLiteSpeed</a></div>";
&ui_print_footer('index.cgi');
