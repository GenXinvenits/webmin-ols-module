# openlitespeed-lib.pl
# Common OpenLiteSpeed functions

BEGIN { push(@INC, ".."); }

use WebminCore;
&init_config();

$config{'lsws'} ||= '/usr/local/lsws';
$config{'lswsctrl'} ||= "$config{'lsws'}/bin/lswsctrl";
$config{'lshttpd'} ||= "$config{'lsws'}/bin/lshttpd";
$config{'config'} ||= "$config{'lsws'}/conf/httpd_config.conf";
$config{'service'} ||= 'lshttpd.service';

sub service_status
{
    my $service = quotemeta($config{'service'});

    my $out = &backquote_command(
        "systemctl is-active $service 2>&1"
    );

    chomp($out);

    return "<font color=green><b>Running</b></font>"
        if $out eq 'active';

    return "<font color=red><b>Stopped</b></font>"
        if $out eq 'inactive';

    return "<font color=red><b>Failed</b></font>"
        if $out eq 'failed';

    return "<b>" . &html_escape($out) . "</b>";
}

sub ols_running
{
    my $service = quotemeta($config{'service'});

    my $out = &backquote_command(
        "systemctl is-active $service 2>&1"
    );

    chomp($out);

    return $out eq 'active' ? 1 : 0;
}

sub ols_version
{
    my $cmd = quotemeta($config{'lshttpd'});

    my $out = &backquote_command(
        "$cmd -v 2>&1"
    );

    if ($out =~ /LiteSpeed\/([^\s]+)/) {
        return $1;
    }

    return "Unknown";
}

sub ols_start
{
    my $service = quotemeta($config{'service'});

    return &system_logged(
        "systemctl start $service",
        1
    );
}

sub ols_stop
{
    my $service = quotemeta($config{'service'});

    return &system_logged(
        "systemctl stop $service",
        1
    );
}

sub ols_restart
{
    my $service = quotemeta($config{'service'});

    return &system_logged(
        "systemctl restart $service",
        1
    );
}

sub ols_list_vhosts
{
    my @rv;
    my $file = $config{'config'};

    return @rv if (!-r $file);

    my @lines = &read_file_lines($file);

    my $vh;

    foreach my $line (@lines) {

        if ($line =~ /^\s*virtualhost\s+(\S+)\s*\{/i) {

            $vh = {
                'name'   => $1,
                'root'   => '',
                'config' => '',
            };

            push(@rv, $vh);
            next;
        }

        next if (!$vh);

        if ($line =~ /^\s*vhRoot\s+(\S+)/i) {
            $vh->{'root'} = $1;
        }
        elsif ($line =~ /^\s*configFile\s+(\S+)/i) {
            $vh->{'config'} = $1;
        }
        elsif ($line =~ /^\s*\}/) {
            $vh = undef;
        }
    }

    return @rv;
}
