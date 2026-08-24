#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ui_print_header(undef, 'OpenLiteSpeed', '');
&ReadParse();

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

sub resolve_value {
    my ($value, $vh) = @_;
    return '' unless defined $value;

    my $vh_root = "$config{'lsws'}/domains/$vh";
    my $server_root = $config{'lsws'};

    $value =~ s/\$VH_NAME/$vh/g;
    $value =~ s/\$VH_ROOT/$vh_root/g;
    $value =~ s/\$SERVER_ROOT/$server_root/g;

    return $value;
}

my $per_page = 20;
my $page = $in{'page'} || 1;
$page =~ s/\D//g;
$page = 1 if !$page || $page < 1;

my $total = scalar @vhosts;
my $pages = $total ? int(($total + $per_page - 1) / $per_page) : 1;
$page = $pages if $page > $pages;

my $start = ($page - 1) * $per_page;
my $end = $start + $per_page - 1;
$end = $total - 1 if $end >= $total;

my $status = &service_status();
my $version = &ols_version();
my $running = &ols_running();

print <<'HTML';
<style>
.ols-wrap { max-width:1200px; margin:0 auto; }
.ols-hero { padding:22px 24px; margin:0 0 20px; border-radius:10px; border:1px solid var(--border-color, rgba(128,128,128,.25)); background:var(--body-bg, transparent); }
.ols-hero-top { display:flex; align-items:flex-start; justify-content:space-between; gap:24px; }
.ols-hero h1 { margin:0 0 5px; font-size:26px; }
.ols-hero p { margin:0; opacity:.72; font-size:13px; }
.ols-details { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:20px; }
.ols-detail { padding:10px 12px; border:1px solid var(--border-color, rgba(128,128,128,.18)); border-radius:7px; }
.ols-detail-label { font-size:10px; text-transform:uppercase; letter-spacing:.05em; opacity:.58; margin-bottom:3px; }
.ols-detail-value { font-size:12px; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ols-controls { display:flex; gap:7px; flex-wrap:wrap; margin-top:18px; }
.ols-control { display:inline-block; padding:7px 12px; border:1px solid var(--border-color, rgba(128,128,128,.25)); border-radius:6px; text-decoration:none; font-size:12px; font-weight:600; }
.ols-control.primary { background:rgba(40,167,69,.12); }
.ols-control.danger { background:rgba(220,53,69,.10); }
.ols-status-running { color:#43b56b; }
.ols-status-stopped { color:#d9534f; }
.ols-list { border:1px solid var(--border-color, rgba(128,128,128,.25)); border-radius:10px; overflow:hidden; background:var(--body-bg, transparent); }
.ols-row { display:grid; grid-template-columns:minmax(220px,1fr) minmax(420px,2.4fr) 150px 100px; align-items:center; gap:16px; padding:13px 16px; border-bottom:1px solid var(--border-color, rgba(128,128,128,.18)); }
.ols-row:last-child { border-bottom:0; }
.ols-head { font-size:11px; text-transform:uppercase; letter-spacing:.05em; font-weight:700; opacity:.68; background:var(--table-header-bg, rgba(128,128,128,.08)); }
.ols-domain { font-weight:700; }
.ols-subdomains { margin-top:3px; font-size:11px; opacity:.65; line-height:1.4; }
.ols-root { font-size:12px; opacity:.72; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ols-meta { font-size:11px; opacity:.72; }
.ols-status { display:inline-block; width:max-content; padding:3px 8px; border-radius:999px; font-size:10px; font-weight:700; background:rgba(40,167,69,.14); color:#43b56b; }
.ols-status.off { background:rgba(128,128,128,.14); color:inherit; opacity:.65; }
.ols-manage { text-align:right; }
.ols-manage a { text-decoration:none; font-weight:600; }
.ols-pagination { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-top:16px; }
.ols-pages { display:flex; gap:5px; flex-wrap:wrap; }
.ols-page { display:inline-block; min-width:30px; padding:6px 9px; text-align:center; border:1px solid var(--border-color, rgba(128,128,128,.25)); border-radius:6px; text-decoration:none; }
.ols-page.current { font-weight:700; background:rgba(128,128,128,.12); }
.ols-server { display:flex; gap:10px; margin-top:22px; flex-wrap:wrap; }
.ols-server a { display:inline-block; padding:8px 13px; border:1px solid var(--border-color, rgba(128,128,128,.25)); border-radius:7px; text-decoration:none; }
.ols-empty { padding:24px; opacity:.72; }
@media(max-width:800px){ .ols-hero-top { flex-direction:column; } .ols-details { grid-template-columns:1fr 1fr; } .ols-row { grid-template-columns:1fr 1fr; } .ols-head { display:none; } .ols-manage { text-align:left; } }
</style>
HTML

print "<div class='ols-wrap'>";

print "<div class='ols-hero'>";
print "<div class='ols-hero-top'>";
print "<div>";
print "<h1>OpenLiteSpeed</h1>";
print "<p>Server status, version, configuration and service controls.</p>";
print "</div>";
print "<div class='ols-meta'>";
if ($running) {
    print "<span class='ols-status-running'><b>● Running</b></span>";
}
else {
    print "<span class='ols-status-stopped'><b>● Stopped</b></span>";
}
print "</div>";
print "</div>";

print "<div class='ols-details'>";
print "<div class='ols-detail'><div class='ols-detail-label'>Status</div><div class='ols-detail-value'>$status</div></div>";
print "<div class='ols-detail'><div class='ols-detail-label'>Version</div><div class='ols-detail-value'>" . &html_escape($version) . "</div></div>";
print "<div class='ols-detail'><div class='ols-detail-label'>Installation</div><div class='ols-detail-value'>" . &html_escape($config{'lsws'}) . "</div></div>";
print "<div class='ols-detail'><div class='ols-detail-label'>Configuration</div><div class='ols-detail-value'>" . &html_escape($config{'config'}) . "</div></div>";
print "</div>";

print "<div class='ols-controls'>";
print "<a class='ols-control primary' href='service.cgi?action=start'>Start</a>";
print "<a class='ols-control danger' href='service.cgi?action=stop'>Stop</a>";
print "<a class='ols-control' href='service.cgi?action=restart'>Restart</a>";
print "<a class='ols-control' href='listeners.cgi'>Listeners</a>";
print "</div>";
print "</div>";

print "<h2>Websites</h2>";
print "<div class='ols-list'>";
print "<div class='ols-row ols-head'>";
print "<div>Domain</div><div>Document Root</div><div>Status</div><div>Action</div>";
print "</div>";

if (!$total) {
    print "<div class='ols-empty'>No virtual hosts were found in <code>" . &html_escape($conf) . "</code>.</div>";
}
else {
    for (my $i = $start; $i <= $end; $i++) {
        my $vh = $vhosts[$i];
        my $root = "$config{'lsws'}/domains/$vh";
        my $vhconf = "$root/conf/vhconf.conf";
        my $conf_exists = -f $vhconf;
        my ($domain, $docroot, $aliases, $php) = ('', '', '', '');
        my $ssl = 0;
        my $rewrite = 0;

        if ($conf_exists) {
            my $content = &read_file_contents($vhconf);
            $domain = resolve_value(get_value($content, 'vhDomain'), $vh);
            $docroot = resolve_value(get_value($content, 'docRoot'), $vh);
            $aliases = resolve_value(get_value($content, 'vhAliases'), $vh);
            $php = $1 if $content =~ /^\s*path\s+(\S+)\s*$/m;
            $ssl = 1 if $content =~ /^\s*vhssl\s*\{/m;
            $rewrite = 1 if $content =~ /^\s*rewrite\s*\{/m;
        }

        $domain = $vh unless $domain;
        $docroot = "$root/public_html" unless $docroot;

        my @subdomains;
        if ($aliases) {
            @subdomains = split(/\s+/, $aliases);
            @subdomains = grep { $_ ne $domain } @subdomains;
        }

        print "<div class='ols-row'>";
        print "<div><div class='ols-domain'>" . &html_escape($domain) . "</div>";
        if (@subdomains) {
            print "<div class='ols-subdomains'>" . &html_escape(join(', ', @subdomains)) . "</div>";
        }
        print "</div>";
        print "<div class='ols-root'>" . &html_escape($docroot) . "</div>";
        print "<div>";
        print $conf_exists ? "<span class='ols-status'>READY</span>" : "<span class='ols-status off'>NOT CONFIGURED</span>";
        print "<div class='ols-meta'>";
        if ($conf_exists) {
            print "SSL " . ($ssl ? 'on' : 'off') . " · Rewrite " . ($rewrite ? 'on' : 'off');
        }
        print "</div></div>";
        print "<div class='ols-manage'>";
        if ($conf_exists) {
            print "<a href='config.cgi?vh=" . &urlize($vh) . "'>Manage →</a>";
        }
        else {
            print "<span class='ols-meta'>Unavailable</span>";
        }
        print "</div>";
        print "</div>";
    }
}

print "</div>";

if ($total > $per_page) {
    print "<div class='ols-pagination'>";
    print "<div class='ols-meta'>Showing " . ($start + 1) . "–" . ($end + 1) . " of $total domains</div>";
    print "<div class='ols-pages'>";

    if ($page > 1) {
        print "<a class='ols-page' href='index.cgi?page=" . ($page - 1) . "'>‹</a>";
    }

    for (my $p = 1; $p <= $pages; $p++) {
        next if $pages > 8 && $p != 1 && $p != $pages && abs($p - $page) > 1;
        print "<a class='ols-page" . ($p == $page ? ' current' : '') . "' href='index.cgi?page=$p'>$p</a>";
    }

    if ($page < $pages) {
        print "<a class='ols-page' href='index.cgi?page=" . ($page + 1) . "'>›</a>";
    }

    print "</div></div>";
}

print "<div class='ols-server'>";
print "<a href='listeners.cgi'>Listeners</a>";
print "</div>";
print "</div>";

&ui_print_footer('', 'index.cgi');
