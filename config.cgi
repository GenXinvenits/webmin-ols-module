#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ui_print_header(undef, 'Virtual Host Configuration', '');
&ReadParse();

my $vh = $in{'vh'} || '';
$vh =~ s/[^A-Za-z0-9._-]//g;

if (!$vh) {
    print "<h2>Virtual Host Configuration</h2>";
    print "<p>No virtual host was specified.</p>";
    print "<a href='index.cgi'>Back to OpenLiteSpeed</a>";
    &ui_print_footer("index.cgi");
    exit;
}

my $vh_root = "$config{'lsws'}/domains/$vh";
my $vh_conf = "$vh_root/conf/vhconf.conf";

if (!-f $vh_conf) {
    print "<h2>Virtual Host Configuration</h2>";
    print "<p>Configuration file does not exist:</p>";
    print "<pre>" . &html_escape($vh_conf) . "</pre>";
    print "<a href='index.cgi'>Back to OpenLiteSpeed</a>";
    &ui_print_footer("index.cgi");
    exit;
}

sub read_tail {
    my ($file, $limit) = @_;
    $limit ||= 100;

    return "Log file does not exist." if !-f $file;
    return "Unable to read log file." if !open(my $fh, '<', $file);

    my @lines;
    while (my $line = <$fh>) {
        push(@lines, $line);
        shift(@lines) while @lines > $limit;
    }
    close($fh);

    return @lines ? join('', @lines) : "Log file is empty.";
}

my $message = '';
my $error = '';

if ($in{'action'} eq 'save') {
    my $new_config = $in{'config'} || '';
    my $timestamp = time();
    my $backup = "$vh_conf.webmin-$timestamp.bak";
    my $tmp = "$vh_conf.webmin-$timestamp.tmp";
    my $old = &read_file_contents($vh_conf);

    if (!open(my $bfh, '>', $backup)) {
        $error = "Unable to create backup: $!";
    }
    else {
        print $bfh $old;
        close($bfh);
    }

    if (!$error) {
        if (!open(my $tfh, '>', $tmp)) {
            $error = "Unable to create temporary configuration: $!";
        }
        else {
            print $tfh $new_config;
            close($tfh);

            if (!rename($tmp, $vh_conf)) {
                $error = "Unable to install temporary configuration: $!";
            }
            else {
                my $test_output = &backquote_command('/usr/local/lsws/bin/lshttpd -t 2>&1');
                my $test_exit = $? >> 8;

                if ($test_exit != 0) {
                    rename($backup, $vh_conf);
                    $error = "OpenLiteSpeed configuration validation failed.";
                    $message = $test_output;
                }
                else {
                    my $restart_output = &backquote_command('/usr/local/lsws/bin/lswsctrl restart 2>&1');
                    my $restart_exit = $? >> 8;

                    if ($restart_exit != 0) {
                        rename($backup, $vh_conf);
                        &backquote_command('/usr/local/lsws/bin/lswsctrl restart 2>&1');
                        $error = "Configuration was restored because OpenLiteSpeed failed to restart.";
                        $message = $restart_output;
                    }
                    else {
                        $message = "Configuration saved, validated and OpenLiteSpeed restarted successfully.";
                    }
                }
            }
        }
    }
}

my $content = &read_file_contents($vh_conf);

sub get_value {
    my ($name) = @_;
    if ($content =~ /^\s*\Q$name\E\s+(.+?)\s*$/m) {
        my $value = $1;
        $value =~ s/\s+$//;
        return $value;
    }
    return '';
}

my $docroot = get_value('docRoot');
my $domain  = get_value('vhDomain');
my $aliases = get_value('vhAliases');

my $php_handler = '';
$php_handler = $1 if $content =~ /^\s*add\s+(\S+)\s+php\s*$/m;

my $php_path = '';
$php_path = $1 if $content =~ /^\s*path\s+(\S+)\s*$/m;

my $php_user = '';
$php_user = $1 if $content =~ /^\s*extUser\s+(\S+)\s*$/m;

my $php_group = '';
$php_group = $1 if $content =~ /^\s*extGroup\s+(\S+)\s*$/m;

my $rewrite = ($content =~ /^\s*rewrite\s*\{/m) ? 'Enabled' : 'Disabled';
my $htaccess = ($content =~ /autoLoadHtaccess\s+1/) ? 'Enabled' : 'Disabled';
my $ssl = ($content =~ /^\s*vhssl\s*\{/m) ? 'Enabled' : 'Disabled';

my $ssl_key = '';
$ssl_key = $1 if $content =~ /^\s*keyFile\s+(\S+)\s*$/m;

my $ssl_cert = '';
$ssl_cert = $1 if $content =~ /^\s*certFile\s+(\S+)\s*$/m;

my $cache = ($content =~ /^\s*module\s+cache\s*\{/m) ? 'Configured' : 'Not configured';

my $access_log = "$vh_root/logs/access.log";
my $error_log  = "$vh_root/logs/error.log";

print "<h2>Virtual Host: " . &html_escape($vh) . "</h2>";

if ($message && !$error) {
    print "<div class='success'><b>" . &html_escape($message) . "</b></div><br>";
}

if ($error) {
    print "<div class='error'><b>" . &html_escape($error) . "</b>";
    print "<pre>" . &html_escape($message) . "</pre>" if $message;
    print "</div><br>";
}

print "<table class='formsection' width='100%'>";
print "<tr><td><b>Virtual Host</b></td><td>" . &html_escape($vh) . "</td></tr>";
print "<tr><td><b>Document Root</b></td><td>" . &html_escape($docroot) . "</td></tr>";
print "<tr><td><b>Domain</b></td><td>" . &html_escape($domain) . "</td></tr>";
print "<tr><td><b>Aliases</b></td><td>" . &html_escape($aliases) . "</td></tr>";
print "<tr><td><b>PHP Handler</b></td><td>" . &html_escape($php_handler) . "</td></tr>";
print "<tr><td><b>PHP Processor</b></td><td>" . &html_escape($php_path) . "</td></tr>";
print "<tr><td><b>PHP User</b></td><td>" . &html_escape($php_user) . "</td></tr>";
print "<tr><td><b>PHP Group</b></td><td>" . &html_escape($php_group) . "</td></tr>";
print "<tr><td><b>Rewrite</b></td><td>$rewrite</td></tr>";
print "<tr><td><b>.htaccess</b></td><td>$htaccess</td></tr>";
print "<tr><td><b>SSL</b></td><td>$ssl</td></tr>";

if ($ssl eq 'Enabled') {
    print "<tr><td><b>SSL Certificate</b></td><td>" . &html_escape($ssl_cert) . "</td></tr>";
    print "<tr><td><b>SSL Key</b></td><td>" . &html_escape($ssl_key) . "</td></tr>";
}

print "<tr><td><b>Cache</b></td><td>$cache</td></tr>";
print "<tr><td><b>Configuration File</b></td><td><code>" . &html_escape($vh_conf) . "</code></td></tr>";
print "</table>";

print "<h2>Domain Logs</h2>";
print "<p>Logs for this virtual host are stored under <code>" . &html_escape("$vh_root/logs/") . "</code>. Showing the last 100 lines.</p>";

print "<details open>";
print "<summary><b>Access Log</b> — " . &html_escape($access_log) . "</summary>";
print "<pre style='width:100%;max-height:450px;overflow:auto;white-space:pre-wrap;'>" .
      &html_escape(read_tail($access_log, 100)) .
      "</pre>";
print "</details>";

print "<br>";

print "<details open>";
print "<summary><b>Error Log</b> — " . &html_escape($error_log) . "</summary>";
print "<pre style='width:100%;max-height:450px;overflow:auto;white-space:pre-wrap;'>" .
      &html_escape(read_tail($error_log, 100)) .
      "</pre>";
print "</details>";

print "<h2>Configuration Editor</h2>";
print "<form method='post' action='config.cgi'>";
print "<input type='hidden' name='vh' value='" . &quote_escape($vh) . "'>";
print "<input type='hidden' name='action' value='save'>";
print "<textarea name='config' style='width:100%;height:650px;font-family:monospace;white-space:pre;tab-size:4;'>" .
      &html_escape($content) .
      "</textarea>";
print "<br><br>";
print "<input type='submit' value='Save Configuration'>";
print "</form>";

print "<br>";
print "<p><b>Safety:</b> A backup is created before every save. The configuration is validated with <code>/usr/local/lsws/bin/lshttpd -t</code> before OpenLiteSpeed is restarted.</p>";
print "<p><a href='index.cgi'>Back to OpenLiteSpeed</a> &nbsp; " .
      &ui_link("config.cgi?vh=" . &urlize($vh), "Refresh Domain") .
      "</p>";

&ui_print_footer("index.cgi");
