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

print <<'HTML';
<style>
.ols-wrap { margin:0 auto; max-width:1200px; }
.ols-hero { padding:24px 28px; margin:0 0 22px; border-radius:12px; background:linear-gradient(135deg,#18243a,#253b5d); color:#fff; box-shadow:0 8px 24px rgba(0,0,0,.12); }
.ols-hero h1 { margin:0 0 6px; font-size:28px; }
.ols-hero p { margin:0; opacity:.82; font-size:14px; }
.ols-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:18px; }
.ols-card { border:1px solid #dfe3e8; border-radius:12px; background:#fff; overflow:hidden; box-shadow:0 3px 12px rgba(0,0,0,.06); }
.ols-card-head { padding:18px 20px; border-bottom:1px solid #edf0f3; display:flex; align-items:center; justify-content:space-between; gap:12px; }
.ols-domain { font-size:18px; font-weight:700; }
.ols-status { font-size:12px; padding:4px 9px; border-radius:20px; background:#e8f7ee; color:#18794e; font-weight:700; }
.ols-status.off { background:#f1f3f5; color:#777; }
.ols-body { padding:16px 20px; }
.ols-root { color:#697386; font-size:12px; margin-bottom:16px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ols-actions { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
.ols-action { display:block; text-align:center; padding:10px 6px; border:1px solid #e1e5ea; border-radius:8px; text-decoration:none; color:#26364a; background:#fafbfc; font-size:12px; font-weight:600; }
.ols-action:hover { background:#f0f4f8; text-decoration:none; }
.ols-meta { display:flex; gap:8px; margin-top:14px; flex-wrap:wrap; }
.ols-pill { font-size:11px; padding:4px 8px; border-radius:5px; background:#f3f5f7; color:#596579; }
.ols-pill.ok { background:#eaf7ef; color:#18794e; }
.ols-server { margin-top:26px; display:flex; flex-wrap:wrap; gap:10px; }
.ols-server a { display:inline-block; padding:11px 16px; border:1px solid #dfe3e8; border-radius:8px; background:#fff; text-decoration:none; font-weight:600; }
@media(max-width:600px){ .ols-grid{grid-template-columns:1fr}.ols-actions{grid-template-columns:repeat(2,1fr)} }
</style>
HTML

print "<div class='ols-wrap'>";
print "<div class='ols-hero'>";
print "<h1>OpenLiteSpeed</h1>";
print "<p>Manage your websites, configurations, SSL, PHP and domain logs from one place.</p>";
print "</div>";

print "<h2>Websites</h2>";

if (!@vhosts) {
    print "<div class='error'>No virtual hosts were found in <code>" . &html_escape($conf) . "</code>.</div>";
}
else {
    print "<div class='ols-grid'>";

    foreach my $vh (@vhosts) {
        my $root = "$config{'lsws'}/domains/$vh";
        my $vhconf = "$root/conf/vhconf.conf";
        my $conf_exists = -f $vhconf;
        my ($domain, $docroot, $php) = ('', '', '');
        my $ssl = 0;
        my $rewrite = 0;

        if ($conf_exists) {
            my $content = &read_file_contents($vhconf);
            $domain = get_value($content, 'vhDomain');
            $docroot = get_value($content, 'docRoot');
            $php = $1 if $content =~ /^\s*path\s+(\S+)\s*$/m;
            $ssl = 1 if $content =~ /^\s*vhssl\s*\{/m;
            $rewrite = 1 if $content =~ /^\s*rewrite\s*\{/m;
        }

        print "<div class='ols-card'>";
        print "<div class='ols-card-head'>";
        print "<span class='ols-domain'>" . &html_escape($domain || $vh) . "</span>";
        print $conf_exists ? "<span class='ols-status'>READY</span>" : "<span class='ols-status off'>NOT CONFIGURED</span>";
        print "</div>";
        print "<div class='ols-body'>";
        print "<div class='ols-root'>" . &html_escape($docroot || 'No document root configured') . "</div>";

        if ($conf_exists) {
            print "<div class='ols-actions'>";
            print "<a class='ols-action' href='config.cgi?vh=" . &urlize($vh) . "'>⚙ Configuration</a>";
            print "<a class='ols-action' href='config.cgi?vh=" . &urlize($vh) . "#logs'>▣ Logs</a>";
            print "<a class='ols-action' href='config.cgi?vh=" . &urlize($vh) . "#ssl'>🔒 SSL</a>";
            print "<a class='ols-action' href='config.cgi?vh=" . &urlize($vh) . "#php'>PHP</a>";
            print "<a class='ols-action' href='config.cgi?vh=" . &urlize($vh) . "#rewrite'>↗ Rewrite</a>";
            print "<a class='ols-action' href='config.cgi?vh=" . &urlize($vh) . "'>Manage →</a>";
            print "</div>";
            print "<div class='ols-meta'>";
            print "<span class='ols-pill ok'>PHP " . &html_escape($php || 'Configured') . "</span>";
            print "<span class='ols-pill" . ($ssl ? " ok" : "") . "">SSL " . ($ssl ? 'Enabled' : 'Disabled') . "</span>";
            print "<span class='ols-pill" . ($rewrite ? " ok" : "") . "">Rewrite " . ($rewrite ? 'Enabled' : 'Disabled') . "</span>";
            print "</div>";
        }
        else {
            print "<div class='ols-actions'><span class='ols-action'>Configuration unavailable</span></div>";
        }

        print "</div></div>";
    }

    print "</div>";
}

print "<h2 style='margin-top:30px'>Server</h2>";
print "<div class='ols-server'>";
print "<a href='listeners.cgi'>⚡ Listeners</a>";
print "<a href='service.cgi?action=restart'>↻ Restart OpenLiteSpeed</a>";
print "</div>";
print "</div>";

&ui_print_footer('', 'index.cgi');
