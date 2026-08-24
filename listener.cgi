#!/usr/bin/perl

require './openlitespeed-lib.pl';

&ui_print_header(undef, 'Listener Configuration', '');

&ReadParse();

my $listener = $in{'listener'} || '';
$listener =~ s/[^A-Za-z0-9._-]//g;

if (!$listener) {
    print "<h2>Listener Configuration</h2>";
    print "<p>No listener was specified.</p>";
    print &ui_link_button("listeners.cgi", "Back to Listeners");
    &ui_print_footer("listeners.cgi");
    exit;
}

my $conf = "$config{'lsws'}/conf/httpd_config.conf";

my $content = '';

if (open(my $fh, '<', $conf)) {
    local $/;
    $content = <$fh>;
    close($fh);
}
else {
    print "<h2>Listener Configuration</h2>";
    print "<div class='error'>Unable to read configuration: " .
          &html_escape($!) .
          "</div>";
    print &ui_link_button("listeners.cgi", "Back to Listeners");
    &ui_print_footer("listeners.cgi");
    exit;
}

sub find_listener_block {
    my ($text, $name) = @_;

    if ($text =~ /(^listener\s+\Q$name\E\s*\{.*?^\})/ms) {
        return $1;
    }

    return '';
}

my $message = '';
my $error = '';

my $block = find_listener_block($content, $listener);

if (!$block) {
    print "<h2>Listener Configuration</h2>";
    print "<p>Listener <b>" .
          &html_escape($listener) .
          "</b> was not found.</p>";
    print &ui_link_button("listeners.cgi", "Back to Listeners");
    &ui_print_footer("listeners.cgi");
    exit;
}

#
# Current listener information
#

my $address = '';

if ($block =~ /^\s*address\s+(.+?)\s*$/m) {
    $address = $1;
}

my $secure = '';

if ($block =~ /^\s*secure\s+(\d+)\s*$/m) {
    $secure = $1;
}

my $protocol =
    ($secure eq '1')
    ? 'HTTPS'
    : 'HTTP';

my $key_file = '';

if ($block =~ /^\s*keyFile\s+(.+?)\s*$/m) {
    $key_file = $1;
}

my $cert_file = '';

if ($block =~ /^\s*certFile\s+(.+?)\s*$/m) {
    $cert_file = $1;
}

#
# SAVE
#
# Only the address line inside the selected listener
# is modified. Everything else is preserved.
#

if ($in{'action'} eq 'save') {

    my $new_address = $in{'address'} || '';

    #
    # Basic validation.
    #
    # Expected examples:
    #
    #   *:80
    #   *:443
    #   0.0.0.0:8080
    #   [::]:8443
    #
    if ($new_address !~ /^(?:\*|0\.0\.0\.0|\[::\]|[0-9A-Fa-f:.]+):[0-9]+$/) {

        $error =
            "Invalid listener address. Use a format such as *:80 or *:443.";

    }
    elsif ($new_address =~ /:(\d+)$/ && ($1 < 1 || $1 > 65535)) {

        $error =
            "Invalid port. The port must be between 1 and 65535.";

    }
    else {

        my $timestamp = time();

        my $backup =
            "$conf.webmin-$timestamp.bak";

        my $tmp =
            "$conf.webmin-$timestamp.tmp";

        #
        # Create complete configuration backup.
        #

        if (!open(my $bfh, '>', $backup)) {

            $error =
                "Unable to create configuration backup: $!";

        }
        else {

            print $bfh $content;
            close($bfh);

            #
            # Replace ONLY the address line belonging
            # to this listener.
            #

            my $new_block = $block;

            if ($new_block =~
                s/^(\s*address\s+)\S+\s*$/$1$new_address/m) {

                my $new_content = $content;

                if ($new_content =~
                    s/\Q$block\E/$new_block/s) {

                    #
                    # Write temporary configuration.
                    #

                    if (!open(my $tfh, '>', $tmp)) {

                        $error =
                            "Unable to create temporary configuration: $!";

                    }
                    else {

                        print $tfh $new_content;
                        close($tfh);

                        #
                        # Validate complete configuration.
                        #

                        my $test_cmd =
                            "/usr/local/lsws/bin/lshttpd -t 2>&1";

                        my $test_output =
                            &backquote_command($test_cmd);

                        my $test_exit = $? >> 8;

                        if ($test_exit != 0) {

                            unlink($tmp);

                            $error =
                                "OpenLiteSpeed configuration validation failed.";

                            $message = $test_output;

                        }
                        else {

                            #
                            # Install validated configuration.
                            #

                            if (!rename($tmp, $conf)) {

                                unlink($tmp);

                                $error =
                                    "Validation succeeded, but the configuration could not be installed: $!";

                            }
                            else {

                                #
                                # Restart OpenLiteSpeed.
                                #

                                my $restart_cmd =
                                    "/usr/local/lsws/bin/lswsctrl restart 2>&1";

                                my $restart_output =
                                    &backquote_command($restart_cmd);

                                my $restart_exit = $? >> 8;

                                if ($restart_exit != 0) {

                                    #
                                    # Restore original configuration.
                                    #

                                    if (open(my $rfh, '>', $conf)) {

                                        print $rfh $content;
                                        close($rfh);
                                    }

                                    &backquote_command(
                                        "/usr/local/lsws/bin/lswsctrl restart 2>&1"
                                    );

                                    $error =
                                        "OpenLiteSpeed failed to restart. The original configuration was restored.";

                                    $message = $restart_output;

                                }
                                else {

                                    $message =
                                        "Listener address saved, validated and OpenLiteSpeed restarted successfully.";

                                    $content = $new_content;

                                    $block =
                                        find_listener_block(
                                            $content,
                                            $listener
                                        );

                                    if ($block =~ /^\s*address\s+(.+?)\s*$/m) {
                                        $address = $1;
                                    }
                                }
                            }
                        }
                    }
                }
                else {

                    $error =
                        "Unable to locate the original listener block in the configuration.";

                }
            }
            else {

                $error =
                    "Unable to locate the listener address line.";

            }
        }
    }
}

#
# Header
#

print "<h2>Listener: " .
      &html_escape($listener) .
      "</h2>";

if ($message && !$error) {

    print "<div class='success'>";
    print "<b>" .
          &html_escape($message) .
          "</b>";
    print "</div><br>";
}

if ($error) {

    print "<div class='error'>";

    print "<b>" .
          &html_escape($error) .
          "</b>";

    if ($message) {

        print "<pre>" .
              &html_escape($message) .
              "</pre>";
    }

    print "</div><br>";
}

#
# Listener information
#

print "<table class='formsection' width='100%'>";

print "<tr>";
print "<td><b>Listener</b></td>";
print "<td>" .
      &html_escape($listener) .
      "</td>";
print "</tr>";

print "<tr>";
print "<td><b>Protocol</b></td>";
print "<td>" .
      &html_escape($protocol) .
      "</td>";
print "</tr>";

print "<tr>";
print "<td><b>Secure</b></td>";
print "<td>" .
      &html_escape($secure) .
      "</td>";
print "</tr>";

if ($secure eq '1') {

    print "<tr>";
    print "<td><b>SSL Certificate</b></td>";
    print "<td><code>" .
          &html_escape($cert_file) .
          "</code></td>";
    print "</tr>";

    print "<tr>";
    print "<td><b>SSL Key</b></td>";
    print "<td><code>" .
          &html_escape($key_file) .
          "</code></td>";
    print "</tr>";
}

print "</table>";

#
# Address editor
#

print "<h2>Listener Address</h2>";

print &ui_form_start("listener.cgi", "post");

print "<input type='hidden' name='listener' value='" .
      &quote_escape($listener) .
      "'>";

print "<input type='hidden' name='action' value='save'>";

print "<table class='formsection' width='100%'>";

print "<tr>";
print "<td><b>Address</b></td>";
print "<td>";

print "<input type='text' name='address' " .
      "value='" . &quote_escape($address) . "' " .
      "style='width:300px;font-family:monospace;'>";

print "<br>";
print "<small>Examples: *:80, *:443, *:8080, *:8443</small>";

print "</td>";
print "</tr>";

print "</table>";

print "<br>";

print &ui_submit("Save Listener");

print " ";

print &ui_link_button("listeners.cgi", "Back to Listeners");

print &ui_form_end();

print "<br>";

print "<p>";
print "<b>Safety:</b> A complete backup of ";
print "<code>httpd_config.conf</code> is created before every save. ";
print "Only the selected listener's <code>address</code> line is changed. ";
print "All virtual-host mappings and other listener settings are preserved. ";
print "The complete resulting configuration is validated with ";
print "<code>/usr/local/lsws/bin/lshttpd -t</code> ";
print "before OpenLiteSpeed is restarted. ";
print "If the restart fails, the original configuration is restored.";
print "</p>";

&ui_print_footer("listeners.cgi");