#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ui_print_header(undef, 'Virtual Host Configuration', '');

&ReadParse();

my $vh = $in{'vh'} || '';
$vh =~ s/[^A-Za-z0-9._-]//g;

if (!$vh) {
    print "<h2>Virtual Host Configuration</h2>";
    print "<p>No virtual host was specified.</p>";
    print "<a href='vhosts.cgi'>Back to Virtual Hosts</a>";
    &ui_print_footer("vhosts.cgi");
    exit;
}

my $vh_root = "$config{'lsws'}/domains/$vh";
my $vh_conf = "$vh_root/conf/vhconf.conf";

if (!-f $vh_conf) {
    print "<h2>Virtual Host Configuration</h2>";
    print "<p>Configuration file does not exist:</p>";
    print "<pre>" . &html_escape($vh_conf) . "</pre>";
    print "<a href='vhosts.cgi'>Back to Virtual Hosts</a>";
    &ui_print_footer("vhosts.cgi");
    exit;
}

my $message = '';
my $error = '';

if ($in{'action'} eq 'save') {

    my $new_config = $in{'config'} || '';

    my $timestamp = time();
    my $backup = "$vh_conf.webmin-$timestamp.bak";
    my $tmp = "$vh_conf.webmin-$timestamp.tmp";

    # Read and preserve the existing configuration.
    my $old = &read_file_contents($vh_conf);

    # Create a backup first.
    if (!open(my $bfh, '>', $backup)) {
        $error = "Unable to create backup: $!";
    }
    else {
        print $bfh $old;
        close($bfh);
    }

    if (!$error) {

        # Write the submitted configuration to a temporary file.
        if (!open(my $tfh, '>', $tmp)) {
            $error = "Unable to create temporary configuration: $!";
        }
        else {
            print $tfh $new_config;
            close($tfh);

            # Temporarily install the candidate configuration.
            if (!rename($tmp, $vh_conf)) {
                $error =
                    "Unable to install temporary configuration: $!";
            }
            else {

                # Validate the actual configuration now installed.
                my $test_cmd =
                    "/usr/local/lsws/bin/lshttpd -t 2>&1";

                my $test_output =
                    &backquote_command($test_cmd);

                my $test_exit = $? >> 8;

                if ($test_exit != 0) {

                    # Restore the known-good configuration.
                    rename($backup, $vh_conf);

                    $error =
                        "OpenLiteSpeed configuration validation failed.";

                    $message = $test_output;
                }
                else {

                    # Configuration is valid. Restart OLS.
                    my $restart_cmd =
                        "/usr/local/lsws/bin/lswsctrl restart 2>&1";

                    my $restart_output =
                        &backquote_command($restart_cmd);

                    my $restart_exit = $? >> 8;

                    if ($restart_exit != 0) {

                        # Restart failed — restore known-good config.
                        rename($backup, $vh_conf);

                        &backquote_command(
                            "/usr/local/lsws/bin/lswsctrl restart 2>&1"
                        );

                        $error =
                            "Configuration was restored because OpenLiteSpeed failed to restart.";

                        $message = $restart_output;
                    }
                    else {
                        $message =
                            "Configuration saved, validated and OpenLiteSpeed restarted successfully.";
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

if ($content =~ /^\s*add\s+(\S+)\s+php\s*$/m) {
    $php_handler = $1;
}

my $php_path = '';

if ($content =~ /^\s*path\s+(\S+)\s*$/m) {
    $php_path = $1;
}

my $php_user = '';

if ($content =~ /^\s*extUser\s+(\S+)\s*$/m) {
    $php_user = $1;
}

my $php_group = '';

if ($content =~ /^\s*extGroup\s+(\S+)\s*$/m) {
    $php_group = $1;
}

my $rewrite =
    ($content =~ /^\s*rewrite\s*\{/m) ?
    'Enabled' : 'Disabled';

my $htaccess =
    ($content =~ /autoLoadHtaccess\s+1/) ?
    'Enabled' : 'Disabled';

my $ssl =
    ($content =~ /^\s*vhssl\s*\{/m) ?
    'Enabled' : 'Disabled';

my $ssl_key = '';

if ($content =~ /^\s*keyFile\s+(\S+)\s*$/m) {
    $ssl_key = $1;
}

my $ssl_cert = '';

if ($content =~ /^\s*certFile\s+(\S+)\s*$/m) {
    $ssl_cert = $1;
}

my $cache =
    ($content =~ /^\s*module\s+cache\s*\{/m) ?
    'Configured' : 'Not configured';

print "<h2>Virtual Host: " .
      &html_escape($vh) .
      "</h2>";

if ($message && !$error) {
    print "<div class='success'>";
    print "<b>" . &html_escape($message) . "</b>";
    print "</div><br>";
}

if ($error) {
    print "<div class='error'>";
    print "<b>" . &html_escape($error) . "</b>";

    if ($message) {
        print "<pre>" .
              &html_escape($message) .
              "</pre>";
    }

    print "</div><br>";
}

print "<table class='formsection' width='100%'>";

print "<tr><td><b>Virtual Host</b></td>";
print "<td>" . &html_escape($vh) . "</td></tr>";

print "<tr><td><b>Document Root</b></td>";
print "<td>" . &html_escape($docroot) . "</td></tr>";

print "<tr><td><b>Domain</b></td>";
print "<td>" . &html_escape($domain) . "</td></tr>";

print "<tr><td><b>Aliases</b></td>";
print "<td>" . &html_escape($aliases) . "</td></tr>";

print "<tr><td><b>PHP Handler</b></td>";
print "<td>" . &html_escape($php_handler) . "</td></tr>";

print "<tr><td><b>PHP Processor</b></td>";
print "<td>" . &html_escape($php_path) . "</td></tr>";

print "<tr><td><b>PHP User</b></td>";
print "<td>" . &html_escape($php_user) . "</td></tr>";

print "<tr><td><b>PHP Group</b></td>";
print "<td>" . &html_escape($php_group) . "</td></tr>";

print "<tr><td><b>Rewrite</b></td>";
print "<td>$rewrite</td></tr>";

print "<tr><td><b>.htaccess</b></td>";
print "<td>$htaccess</td></tr>";

print "<tr><td><b>SSL</b></td>";
print "<td>$ssl</td></tr>";

if ($ssl eq 'Enabled') {

    print "<tr><td><b>SSL Certificate</b></td>";
    print "<td>" . &html_escape($ssl_cert) . "</td></tr>";

    print "<tr><td><b>SSL Key</b></td>";
    print "<td>" . &html_escape($ssl_key) . "</td></tr>";
}

print "<tr><td><b>Cache</b></td>";
print "<td>$cache</td></tr>";

print "<tr><td><b>Configuration File</b></td>";
print "<td><code>" .
      &html_escape($vh_conf) .
      "</code></td></tr>";

print "</table>";

print "<br>";

print "<form method='post' action='config.cgi'>";
print "<input type='hidden' name='vh' value='" .
      &html_escape($vh) . "'>";
print "<input type='hidden' name='action' value='save'>";

print "<h2>Configuration Editor</h2>";

print "<textarea name='config' " .
      "style='width:100%;height:650px;" .
      "font-family:monospace;white-space:pre;" .
      "tab-size:4;'>" .
      &html_escape($content) .
      "</textarea>";

print "<br><br>";

print "<input type='submit' value='Save Configuration'>";

print " ";

print "<a href='vhosts.cgi'>Back to Virtual Hosts</a>";

print "</form>";

print "<br>";

print "<p>";
print "<b>Safety:</b> A backup is created before every save. ";
print "The configuration is validated with ";
print "<code>/usr/local/lsws/bin/lshttpd -t</code> ";
print "before OpenLiteSpeed is restarted.";
print "</p>";

&ui_print_footer("vhosts.cgi");
