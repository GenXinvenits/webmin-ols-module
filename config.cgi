#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'Virtual Host Configuration', '');
&ReadParse();

my $vh = $in{'vh'} || '';
$vh =~ s/[^A-Za-z0-9._-]//g;

if (!$vh) {
    print "<h2>Virtual Host Configuration</h2><p>No virtual host was specified.</p><a href='index.cgi'>Back to OpenLiteSpeed</a>";
    &ui_print_footer('index.cgi'); exit;
}

my $vh_root = "$config{'lsws'}/domains/$vh";
my $vh_conf = "$vh_root/conf/vhconf.conf";

if (!-f $vh_conf) {
    print "<h2>Virtual Host Configuration</h2><p>Configuration file does not exist:</p><pre>" . &html_escape($vh_conf) . "</pre><a href='index.cgi'>Back to OpenLiteSpeed</a>";
    &ui_print_footer('index.cgi'); exit;
}

sub read_tail {
    my ($file, $limit) = @_;
    return "Log file does not exist." if !-f $file;
    return "Unable to read log file." if !open(my $fh, '<', $file);
    my @lines;
    while (my $line = <$fh>) { push @lines, $line; shift(@lines) while @lines > ($limit || 100); }
    close($fh);
    return @lines ? join('', @lines) : 'Log file is empty.';
}

my $message = '';
my $error = '';

if ($in{'action'} eq 'save') {
    my $new_config = $in{'config'} || '';
    my $timestamp = time();
    my $backup = "$vh_conf.webmin-$timestamp.bak";
    my $tmp = "$vh_conf.webmin-$timestamp.tmp";
    my $old = &read_file_contents($vh_conf);

    if (!open(my $bfh, '>', $backup)) { $error = "Unable to create backup: $!"; }
    else { print $bfh $old; close($bfh); }

    if (!$error) {
        if (!open(my $tfh, '>', $tmp)) { $error = "Unable to create temporary configuration: $!"; }
        else {
            print $tfh $new_config; close($tfh);
            if (!rename($tmp, $vh_conf)) { $error = "Unable to install temporary configuration: $!"; }
            else {
                my $test_output = &backquote_command('/usr/local/lsws/bin/lshttpd -t 2>&1');
                my $test_exit = $? >> 8;
                if ($test_exit != 0) {
                    rename($backup, $vh_conf);
                    $error = 'OpenLiteSpeed configuration validation failed.'; $message = $test_output;
                } else {
                    my $restart_output = &backquote_command('/usr/local/lsws/bin/lswsctrl restart 2>&1');
                    my $restart_exit = $? >> 8;
                    if ($restart_exit != 0) {
                        rename($backup, $vh_conf);
                        &backquote_command('/usr/local/lsws/bin/lswsctrl restart 2>&1');
                        $error = 'Configuration was restored because OpenLiteSpeed failed to restart.'; $message = $restart_output;
                    } else { $message = 'Configuration saved, validated and OpenLiteSpeed restarted successfully.'; }
                }
            }
        }
    }
}

my $content = &read_file_contents($vh_conf);
sub get_value {
    my ($name) = @_;
    if ($content =~ /^\s*\Q$name\E\s+(.+?)\s*$/m) { my $v=$1; $v =~ s/\s+$//; return $v; }
    return '';
}

my $docroot=get_value('docRoot'); my $domain=get_value('vhDomain'); my $aliases=get_value('vhAliases');
my $php_handler = ($content =~ /^\s*add\s+(\S+)\s+php\s*$/m) ? $1 : '';
my $php_path = ($content =~ /^\s*path\s+(\S+)\s*$/m) ? $1 : '';
my $php_user = ($content =~ /^\s*extUser\s+(\S+)\s*$/m) ? $1 : '';
my $php_group = ($content =~ /^\s*extGroup\s+(\S+)\s*$/m) ? $1 : '';
my $rewrite = ($content =~ /^\s*rewrite\s*\{/m) ? 'Enabled' : 'Disabled';
my $htaccess = ($content =~ /autoLoadHtaccess\s+1/) ? 'Enabled' : 'Disabled';
my $ssl = ($content =~ /^\s*vhssl\s*\{/m) ? 'Enabled' : 'Disabled';
my $ssl_key = ($content =~ /^\s*keyFile\s+(\S+)\s*$/m) ? $1 : '';
my $ssl_cert = ($content =~ /^\s*certFile\s+(\S+)\s*$/m) ? $1 : '';
my $cache = ($content =~ /^\s*module\s+cache\s*\{/m) ? 'Configured' : 'Not configured';
my $access_log="$vh_root/logs/access.log"; my $error_log="$vh_root/logs/error.log";

print <<'HTML';
<style>
.ols-vh { max-width:1200px; margin:0 auto; }
.ols-vh-hero { padding:24px 28px; border-radius:12px; background:linear-gradient(135deg,#18243a,#253b5d); color:#fff; box-shadow:0 8px 24px rgba(0,0,0,.12); }
.ols-vh-hero h1 { margin:0 0 5px; font-size:27px; }
.ols-vh-hero p { margin:0; opacity:.8; }
.ols-tabs { display:flex; flex-wrap:wrap; gap:6px; margin:18px 0; padding:7px; background:#f2f4f7; border-radius:10px; }
.ols-tabs a { padding:9px 14px; border-radius:7px; text-decoration:none; font-weight:600; font-size:13px; color:#445066; }
.ols-tabs a:hover { background:#fff; }
.ols-section { background:#fff; border:1px solid #e0e4e9; border-radius:11px; margin:0 0 18px; overflow:hidden; }
.ols-section h2 { margin:0; padding:15px 20px; border-bottom:1px solid #edf0f3; font-size:17px; }
.ols-section-body { padding:18px 20px; }
.ols-info { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:1px; background:#e5e8ec; border:1px solid #e5e8ec; border-radius:8px; overflow:hidden; }
.ols-info div { background:#fff; padding:13px 15px; }
.ols-label { display:block; color:#778196; font-size:11px; text-transform:uppercase; letter-spacing:.05em; margin-bottom:4px; }
.ols-value { font-weight:600; word-break:break-word; }
.ols-badge { display:inline-block; padding:4px 9px; border-radius:20px; background:#eaf7ef; color:#18794e; font-size:12px; font-weight:700; }
.ols-badge.off { background:#f1f3f5; color:#737b87; }
.ols-log { margin:0; padding:15px; max-height:430px; overflow:auto; white-space:pre-wrap; background:#111827; color:#d7dee8; border-radius:8px; font:12px/1.55 monospace; }
.ols-log-title { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; font-weight:700; }
.ols-editor { width:100%; min-height:620px; box-sizing:border-box; font-family:monospace; font-size:12px; line-height:1.5; padding:14px; border:1px solid #ccd2da; border-radius:8px; background:#111827; color:#e5e7eb; }
.ols-save { padding:10px 18px; border:0; border-radius:7px; cursor:pointer; font-weight:700; }
.ols-note { color:#687386; font-size:12px; }
@media(max-width:600px){.ols-vh-hero{padding:20px}.ols-tabs{overflow:auto;flex-wrap:nowrap}.ols-tabs a{white-space:nowrap}}
</style>
HTML

print "<div class='ols-vh'>";
print "<div class='ols-vh-hero'><h1>" . &html_escape($domain || $vh) . "</h1><p>Virtual host management</p></div>";

if ($message && !$error) { print "<div class='success' style='margin-top:16px'><b>" . &html_escape($message) . "</b></div>"; }
if ($error) { print "<div class='error' style='margin-top:16px'><b>" . &html_escape($error) . "</b>"; print "<pre>".&html_escape($message)."</pre>" if $message; print "</div>"; }

print "<nav class='ols-tabs'>";
print "<a href='#overview'>Overview</a><a href='#php'>PHP</a><a href='#ssl'>SSL</a><a href='#rewrite'>Rewrite</a><a href='#logs'>Logs</a><a href='#editor'>Advanced Configuration</a><a href='index.cgi'>← All Websites</a>";
print "</nav>";

print "<section class='ols-section' id='overview'><h2>Overview</h2><div class='ols-section-body'><div class='ols-info'>";
sub info { my ($label,$value)=@_; print "<div><span class='ols-label'>".&html_escape($label)."</span><span class='ols-value'>".&html_escape($value || '—')."</span></div>"; }
info('Virtual Host',$vh); info('Domain',$domain); info('Aliases',$aliases); info('Document Root',$docroot); info('Cache',$cache); info('Configuration File',$vh_conf);
print "</div></div></section>";

print "<section class='ols-section' id='php'><h2>PHP</h2><div class='ols-section-body'><div class='ols-info'>";
info('Handler',$php_handler); info('Processor',$php_path); info('User',$php_user); info('Group',$php_group);
print "</div></div></section>";

print "<section class='ols-section' id='ssl'><h2>SSL / HTTPS</h2><div class='ols-section-body'><div class='ols-info'>";
print "<div><span class='ols-label'>Status</span><span class='ols-badge".($ssl eq 'Enabled'?'':' off')."'>$ssl</span></div>";
info('Certificate',$ssl_cert); info('Private Key',$ssl_key);
print "</div></div></section>";

print "<section class='ols-section' id='rewrite'><h2>Rewrite</h2><div class='ols-section-body'><div class='ols-info'>";
print "<div><span class='ols-label'>Rewrite</span><span class='ols-badge".($rewrite eq 'Enabled'?'':' off')."'>$rewrite</span></div>";
print "<div><span class='ols-label'>.htaccess</span><span class='ols-badge".($htaccess eq 'Enabled'?'':' off')."'>$htaccess</span></div>";
print "</div></div></section>";

print "<section class='ols-section' id='logs'><h2>Domain Logs</h2><div class='ols-section-body'>";
print "<p class='ols-note'>Only logs belonging to <b>".&html_escape($vh)."</b> are shown. Displaying the latest 100 lines.</p>";
print "<details open><summary class='ols-log-title'>Access Log</summary><pre class='ols-log'>".&html_escape(read_tail($access_log,100))."</pre></details><br>";
print "<details open><summary class='ols-log-title'>Error Log</summary><pre class='ols-log'>".&html_escape(read_tail($error_log,100))."</pre></details>";
print "</div></section>";

print "<section class='ols-section' id='editor'><h2>Advanced Configuration</h2><div class='ols-section-body'>";
print "<p class='ols-note'>For advanced OpenLiteSpeed directives. A backup is created before saving, the complete server configuration is validated, and OpenLiteSpeed is restarted only after validation succeeds.</p>";
print "<form method='post' action='config.cgi'>";
print "<input type='hidden' name='vh' value='".&quote_escape($vh)."'><input type='hidden' name='action' value='save'>";
print "<textarea class='ols-editor' name='config'>".&html_escape($content)."</textarea><br><br>";
print "<input class='ols-save' type='submit' value='Save Configuration'>";
print "</form></div></section>";

print "</div>";
&ui_print_footer('index.cgi');
