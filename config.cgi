#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'Virtual Host Management', '');
&ReadParse();

my $vh = $in{'vh'} || '';
$vh =~ s/[^A-Za-z0-9._-]//g;

if (!$vh) {
    print "<h2>Virtual Host Management</h2><p>No virtual host was specified.</p><a href='index.cgi'>Back to OpenLiteSpeed</a>";
    &ui_print_footer('index.cgi'); exit;
}

my $vh_root = "$config{'lsws'}/domains/$vh";
my $vh_conf = "$vh_root/conf/vhconf.conf";

if (!-f $vh_conf) {
    print "<h2>Virtual Host Management</h2><p>Configuration file does not exist:</p><pre>" . &html_escape($vh_conf) . "</pre><a href='index.cgi'>Back to OpenLiteSpeed</a>";
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

sub resolve_value {
    my ($value) = @_;
    return '' unless defined $value;
    my $server_root = $config{'lsws'};
    $value =~ s/\$VH_NAME/$vh/g;
    $value =~ s/\$VH_ROOT/$vh_root/g;
    $value =~ s/\$SERVER_ROOT/$server_root/g;
    return $value;
}

my $docroot=resolve_value(get_value('docRoot')); my $domain=resolve_value(get_value('vhDomain')); my $aliases=resolve_value(get_value('vhAliases'));
$domain = $vh if !$domain || $domain eq '$VH_NAME';
$domain = $vh if !$domain;
$docroot = "$vh_root/public_html" if !$docroot || $docroot eq '$VH_ROOT/public_html';
my $php_handler = ($content =~ /^\s*add\s+(\S+)\s+php\s*$/m) ? $1 : '';
my $php_path = ($content =~ /^\s*path\s+(\S+)\s*$/m) ? $1 : '';
my $php_user = ($content =~ /^\s*extUser\s+(\S+)\s*$/m) ? $1 : '';
my $php_group = ($content =~ /^\s*extGroup\s+(\S+)\s*$/m) ? $1 : '';

my $php_version = '';
if ($php_path =~ m{(?:^|/)lsphp(\d)(\d)(?:/|$)}) {
    $php_version = "$1.$2";
}

my $rewrite = ($content =~ /^\s*rewrite\s*\{/m) ? 'Enabled' : 'Disabled';
my $htaccess = ($content =~ /autoLoadHtaccess\s+1/) ? 'Enabled' : 'Disabled';
my $ssl = ($content =~ /^\s*vhssl\s*\{/m) ? 'Enabled' : 'Disabled';
my $ssl_key = ($content =~ /^\s*keyFile\s+(\S+)\s*$/m) ? $1 : '';
my $ssl_cert = ($content =~ /^\s*certFile\s+(\S+)\s*$/m) ? $1 : '';
my $cache = ($content =~ /^\s*module\s+cache\s*\{/m) ? 'Configured' : 'Not configured';
my $access_log="$vh_root/logs/access.log"; my $error_log="$vh_root/logs/error.log";

print <<'HTML';
<style>
.ols-vh{max-width:1180px;margin:0 auto}.ols-hero{padding:28px 30px;border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:14px;background:var(--body-bg,transparent);box-shadow:0 8px 24px rgba(0,0,0,.06)}.ols-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.08em;opacity:.58;font-weight:700}.ols-hero h1{margin:6px 0 5px;font-size:30px}.ols-hero p{margin:0;opacity:.65;font-size:13px}.ols-tabs{display:flex;gap:4px;flex-wrap:wrap;margin:18px 0;padding:5px;border:1px solid var(--border-color,rgba(128,128,128,.2));border-radius:10px;background:rgba(128,128,128,.06)}.ols-tabs button{padding:9px 13px;border:0;border-radius:7px;background:transparent;color:inherit;font:inherit;font-weight:600;font-size:12px;opacity:.78;cursor:pointer}.ols-tabs button:hover,.ols-tabs button.active{background:rgba(128,128,128,.12);opacity:1}.ols-tabs .back{margin-left:auto;text-decoration:none;padding:9px 13px;font-weight:600;font-size:12px;opacity:.78}.ols-panel{display:none}.ols-panel.active{display:block}.ols-section{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:12px;margin-bottom:16px;overflow:hidden;background:var(--body-bg,transparent)}.ols-section h2{margin:0;padding:16px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16));font-size:16px}.ols-body{padding:18px 20px}.ols-info{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;border:1px solid var(--border-color,rgba(128,128,128,.18));border-radius:9px;overflow:hidden;background:var(--border-color,rgba(128,128,128,.18))}.ols-info>div{padding:14px 15px;background:var(--body-bg,transparent);min-width:0}.ols-label{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.06em;opacity:.52;margin-bottom:5px}.ols-value{font-size:13px;font-weight:600;word-break:break-word}.ols-badge{display:inline-block;padding:4px 9px;border-radius:999px;background:rgba(40,167,69,.13);color:#39a866;font-size:11px;font-weight:700}.ols-badge.off{background:rgba(128,128,128,.12);color:#888}.ols-log{margin:0;padding:15px;max-height:420px;overflow:auto;white-space:pre-wrap;background:#111827;color:#d7dee8;border-radius:8px;font:12px/1.55 monospace}.ols-log-title{font-weight:700;margin:0 0 9px;cursor:pointer}.ols-editor{width:100%;min-height:620px;box-sizing:border-box;font:12px/1.5 monospace;padding:14px;border:1px solid var(--border-color,rgba(128,128,128,.3));border-radius:9px;background:#111827;color:#e5e7eb}.ols-save{padding:10px 18px;border:0;border-radius:7px;cursor:pointer;font-weight:700}.ols-note{font-size:12px;opacity:.62;margin-top:0}.ols-message{margin:16px 0;padding:12px 15px;border-radius:8px}.ols-success{background:rgba(40,167,69,.1);border:1px solid rgba(40,167,69,.25)}.ols-error{background:rgba(220,53,69,.1);border:1px solid rgba(220,53,69,.25)}@media(max-width:700px){.ols-info{grid-template-columns:1fr}.ols-hero{padding:22px}.ols-tabs{overflow:auto;flex-wrap:nowrap}.ols-tabs button,.ols-tabs .back{white-space:nowrap}.ols-tabs .back{margin-left:0}}
</style>
<script>
(function(){
  function activate(name, updateHash){
    var panels=document.querySelectorAll('.ols-panel');
    var buttons=document.querySelectorAll('.ols-tab');
    for(var i=0;i<panels.length;i++) panels[i].classList.toggle('active',panels[i].id===name);
    for(var j=0;j<buttons.length;j++) buttons[j].classList.toggle('active',buttons[j].getAttribute('data-tab')===name);
    if(updateHash && window.history && history.replaceState) history.replaceState(null,'','#'+name);
  }
  function initial(){
    var hash=(window.location.hash||'').substring(1);
    var valid=['overview','php','ssl','rewrite','logs','editor'];
    activate(valid.indexOf(hash)>=0?hash:'overview',false);
  }
  window.olsShowTab=function(name){ activate(name,true); };
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded',initial);
  else initial();
  window.addEventListener('hashchange',function(){ initial(); });
})();
</script>
HTML

print "<div class='ols-vh'>";
print "<div class='ols-hero'><span class='ols-kicker'>Virtual host</span><h1>".&html_escape($domain || $vh)."</h1><p>Manage website configuration, PHP, SSL, rewrite rules and domain logs.</p></div>";
if ($message && !$error) { print "<div class='ols-message ols-success'>".&html_escape($message)."</div>"; }
if ($error) { print "<div class='ols-message ols-error'><b>".&html_escape($error)."</b>"; print "<pre>".&html_escape($message)."</pre>" if $message; print "</div>"; }

print "<nav class='ols-tabs'><button type='button' class='ols-tab active' data-tab='overview' onclick=\"olsShowTab('overview')\">Overview</button><button type='button' class='ols-tab' data-tab='php' onclick=\"olsShowTab('php')\">PHP</button><button type='button' class='ols-tab' data-tab='ssl' onclick=\"olsShowTab('ssl')\">SSL</button><button type='button' class='ols-tab' data-tab='rewrite' onclick=\"olsShowTab('rewrite')\">Rewrite</button><button type='button' class='ols-tab' data-tab='logs' onclick=\"olsShowTab('logs')\">Logs</button><button type='button' class='ols-tab' data-tab='editor' onclick=\"olsShowTab('editor')\">Advanced</button><a class='back' href='index.cgi'>← All Websites</a></nav>";

sub info { my ($label,$value)=@_; print "<div><span class='ols-label'>".&html_escape($label)."</span><span class='ols-value'>".&html_escape($value || '—')."</span></div>"; }

print "<div class='ols-panel active' id='overview'><section class='ols-section'><h2>Website Overview</h2><div class='ols-body'><div class='ols-info'>";
info('Virtual Host',$vh); info('Domain',$domain); info('Aliases',$aliases); info('Document Root',$docroot); info('Cache',$cache); info('Configuration',$vh_conf);
print "</div></div></section></div>";

print "<div class='ols-panel' id='php'><section class='ols-section'><h2>PHP Runtime</h2><div class='ols-body'><div class='ols-info'>";
info('PHP Version',$php_version || 'Not detected'); info('Handler',$php_handler); info('Processor',$php_path); info('User',$php_user); info('Group',$php_group);
print "</div></div></section></div>";

print "<div class='ols-panel' id='ssl'><section class='ols-section'><h2>SSL / HTTPS</h2><div class='ols-body'><div class='ols-info'>";
print "<div><span class='ols-label'>Status</span><span class='ols-badge".($ssl eq 'Enabled'?'':' off')."'>".&html_escape($ssl)."</span></div>";
info('Certificate',$ssl_cert); info('Private Key',$ssl_key);
print "</div></div></section></div>";

print "<div class='ols-panel' id='rewrite'><section class='ols-section'><h2>Rewrite &amp; .htaccess</h2><div class='ols-body'><div class='ols-info'>";
print "<div><span class='ols-label'>Rewrite</span><span class='ols-badge".($rewrite eq 'Enabled'?'':' off')."'>".$rewrite."</span></div>";
print "<div><span class='ols-label'>.htaccess</span><span class='ols-badge".($htaccess eq 'Enabled'?'':' off')."'>".$htaccess."</span></div>";
print "</div></div></section></div>";

print "<div class='ols-panel' id='logs'><section class='ols-section'><h2>Domain Logs</h2><div class='ols-body'><p class='ols-note'>Latest 100 lines from logs belonging only to this virtual host.</p>";
print "<details open><summary class='ols-log-title'>Access Log</summary><pre class='ols-log'>".&html_escape(read_tail($access_log,100))."</pre></details><br>";
print "<details open><summary class='ols-log-title'>Error Log</summary><pre class='ols-log'>".&html_escape(read_tail($error_log,100))."</pre></details></div></section></div>";

print "<div class='ols-panel' id='editor'><section class='ols-section'><h2>Advanced Configuration</h2><div class='ols-body'><p class='ols-note'>Edit the complete virtual-host configuration. A backup is created before saving, the resulting server configuration is validated, and OpenLiteSpeed is restarted only after successful validation.</p>";
print "<form method='post' action='config.cgi'><input type='hidden' name='vh' value='".&quote_escape($vh)."'><input type='hidden' name='action' value='save'><textarea class='ols-editor' name='config'>".&html_escape($content)."</textarea><br><br><input class='ols-save' type='submit' value='Save Configuration'></form></div></section></div>";

print "</div>";
&ui_print_footer('');