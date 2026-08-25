#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'Domain Management', '');
&ReadParse();

use File::Path qw(make_path remove_tree);
use File::Basename qw(dirname);

my $conf = "$config{'lsws'}/conf/httpd_config.conf";
my $domain_base = '/var/www/domains';
my $message = '';
my $error = '';

sub read_config {
    return '' unless -f $conf;
    return &read_file_contents($conf);
}

sub vhost_names {
    my ($text) = @_;
    my @names;
    while ($text =~ /^\s*virtualhost\s+(\S+)\s*\{/mg) { push @names, $1; }
    return @names;
}

sub valid_domain {
    my ($d) = @_;
    return $d =~ /^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$/;
}

sub valid_alias_prefixes {
    my ($s) = @_;
    return 1 unless defined $s && length $s;
    for my $prefix (split(/[\s,]+/, $s)) {
        next unless length $prefix;
        return 0 unless $prefix =~ /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/;
    }
    return 1;
}

sub build_aliases {
    my ($domain, $prefixes) = @_;
    my @aliases;
    my %seen;
    my $www = 'www.' . lc($domain);
    push @aliases, $www;
    $seen{$www} = 1;
    for my $prefix (split(/[\s,]+/, $prefixes || '')) {
        next unless length $prefix;
        my $alias = lc($prefix) . '.' . lc($domain);
        next if $alias eq lc($domain) || $seen{$alias}++;
        push @aliases, $alias;
    }
    return join(' ', @aliases);
}

sub add_listener_maps {
    my ($text, $vh, $aliases) = @_;
    my @maps;
    my %seen;
    for my $alias (split(/\s+/, $aliases || '')) {
        next unless length $alias;
        next if lc($alias) eq lc($vh);
        next if $seen{lc($alias)}++;
        push @maps, "    map $vh $alias\n";
    }
    return $text unless @maps;
    my $maps = join('', @maps);
    if ($text =~ /(^\s*listener\s+\S+\s*\{.*?)(^\})/ms) {
        $text =~ s{(^\s*listener\s+\S+\s*\{.*?)(^\})}{$1$maps$2}ms;
    }
    return $text;
}

sub remove_listener_maps {
    my ($text, $vh) = @_;
    $text =~ s/^\s*map\s+\Q$vh\E\s+.*?\n//mg;
    return $text;
}

sub remove_vhost_block {
    my ($text, $vh) = @_;
    my @lines = split(/(?<=\n)/, $text, -1);
    my @out;
    my $skip = 0;
    my $depth = 0;
    my $found = 0;
    for my $line (@lines) {
        if (!$skip && $line =~ /^\s*virtualhost\s+\Q$vh\E\s*\{/i) {
            $skip = 1;
            $found = 1;
            $depth = 0;
        }
        if ($skip) {
            my $opens = () = $line =~ /\{/g;
            my $closes = () = $line =~ /\}/g;
            $depth += $opens - $closes;
            $skip = 0 if $depth <= 0;
            next;
        }
        push @out, $line;
    }
    return (join('', @out), $found);
}

sub find_lsphp {
    my @paths;
    if (opendir(my $dh, $config{'lsws'})) {
        while (my $entry = readdir($dh)) {
            push @paths, "$config{'lsws'}/$entry/bin/lsphp" if $entry =~ /^lsphp[0-9.]+$/;
        }
        closedir($dh);
    }
    for my $p (sort { $b cmp $a } @paths) { return $p if -x $p; }
    return '';
}

sub load_vh_template {
    my $template = dirname(__FILE__) . '/templates/vhost.conf.template';
    return (0, "The OpenLiteSpeed vhost template is missing: $template") unless -f $template;
    my $content = &read_file_contents($template);
    return (0, "Unable to read the OpenLiteSpeed vhost template: $template") unless defined $content;
    return (1, $content);
}

sub certbot_path {
    for my $p ('/usr/bin/certbot','/usr/local/bin/certbot','/bin/certbot') { return $p if -x $p; }
    for my $dir (split(/:/, $ENV{'PATH'} || '')) {
        next unless $dir;
        my $p = "$dir/certbot";
        return $p if -x $p;
    }
    return '';
}

sub openssl_path {
    for my $p ('/usr/bin/openssl','/usr/local/bin/openssl','/bin/openssl') { return $p if -x $p; }
    return '';
}

sub quote_shell_command {
    my ($s) = @_;
    $s = '' unless defined $s;
    $s =~ s/'/'\\''/g;
    return "'$s'";
}

sub run_command {
    my ($cmd) = @_;
    my $out = &backquote_command($cmd . ' 2>&1');
    return (($? >> 8), $out);
}

sub install_certificate {
    my ($src_cert, $src_key, $cert_root) = @_;
    return 0 unless -f $src_cert && -f $src_key;
    eval { make_path($cert_root) unless -d $cert_root; 1 } or return 0;
    my $fullchain = "$cert_root/fullchain.pem";
    my $privkey = "$cert_root/privkey.pem";
    return 0 unless system('/bin/cp','-f',$src_cert,$fullchain) == 0;
    return 0 unless system('/bin/cp','-f',$src_key,$privkey) == 0;
    chmod(0600, $privkey);
    chmod(0644, $fullchain);
    return (-f $fullchain && -f $privkey);
}

sub generate_self_signed {
    my ($domain, $aliases, $cert_root) = @_;
    my $openssl = openssl_path();
    return (0, 'OpenSSL is not installed.') unless $openssl;
    my $tmp = "/tmp/webmin-ols-domain-ssl-$$";
    make_path($tmp);
    my $key = "$tmp/privkey.pem";
    my $crt = "$tmp/cert.pem";
    my $cnf = "$tmp/openssl.cnf";
    my @names = ($domain, split(/\s+/, $aliases || ''));
    my $san = join(',', map { 'DNS:' . $_ } @names);
    my $ok = 0;
    if (open(my $fh, '>', $cnf)) {
        print $fh "[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=v3\n[dn]\nCN=$domain\n[v3]\nsubjectAltName=$san\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n";
        close($fh);
        my ($e1,$out) = run_command(quote_shell_command($openssl).' genrsa -out '.quote_shell_command($key).' 2048');
        my ($e2,$out2) = run_command(quote_shell_command($openssl).' req -new -x509 -sha256 -key '.quote_shell_command($key).' -out '.quote_shell_command($crt).' -days 3650 -config '.quote_shell_command($cnf));
        $out .= $out2;
        $ok = !$e1 && !$e2 && install_certificate($crt,$key,$cert_root);
        unlink($key,$crt,$cnf);
        rmdir($tmp);
        return ($ok, $ok ? '' : "Self-signed certificate generation failed.\n$out");
    }
    rmdir($tmp);
    return (0, 'Unable to create the temporary OpenSSL configuration.');
}

sub add_vhssl_block {
    my ($content) = @_;
    return $content if $content =~ /^\s*vhssl\s*\{/m;
    my $ssl = <<'SSL';

vhssl {
  keyFile                       $SERVER_ROOT/cert/$VH_NAME/privkey.pem
  certFile                      $SERVER_ROOT/cert/$VH_NAME/fullchain.pem
  certChain                     1
  sslSessionCache               1
  sslSessionTickets             0
  renegProtection               1
  enableQuic                    0
}
SSL
    if ($content =~ /\nmodule cache\s*\{/m) { $content =~ s/\nmodule cache\s*\{/\n$ssl\nmodule cache {/m; }
    else { $content .= $ssl; }
    return $content;
}

sub remove_vhssl_block {
    my ($content) = @_;
    $content =~ s/\n?vhssl\s*\{.*?\n\}\n//s;
    return $content;
}

sub build_vhconf {
    my ($domain, $aliases, $ssl_mode) = @_;
    my ($ok, $template) = load_vh_template();
    return '' unless $ok;
    my $lsphp = find_lsphp();
    my $php = '';
    if ($lsphp) {
        $php = <<"PHP";

scripthandler {
  add                           lsapi:www-data php
}

extprocessor www-data {
  type                          lsapi
  address                       UDS://tmp/lshttpd/www-data.sock
  maxConns                      2
  env                           LSAPI_CHILDREN=2
  env                           LSAPI_AVOID_FORK=200M
  env                           LSAPI_MAX_IDLE=30
  initTimeout                   30
  retryTimeout                  0
  persistConn                   1
  pcKeepAliveTimeout            2
  respBuffer                    0
  autoStart                     1
  runOnStartUp                  1
  path                          $lsphp
  extUser                       www-data
  extGroup                      www-data
  memSoftLimit                  128M
  memHardLimit                  160M
  procSoftLimit                 10
  procHardLimit                 15
}
PHP
    }
    my $alias_line = $aliases ? "vhAliases                      $aliases\n" : '';
    $template =~ s/__DOMAIN__/$domain/g;
    $template =~ s/__VH_ALIASES_LINE__/$alias_line/;
    $template =~ s/__PHP_CONFIG__/$php/;
    $template = remove_vhssl_block($template) if !$ssl_mode || $ssl_mode eq 'none';
    return $template;
}

sub apply_global_config {
    my ($old, $new) = @_;
    my $timestamp = time();
    my $backup = "$conf.webmin-$timestamp.bak";
    my $tmp = "$conf.webmin-$timestamp.tmp";
    open(my $bfh, '>', $backup) or return (0, "Unable to create configuration backup: $!");
    print $bfh $old;
    close($bfh);
    open(my $tfh, '>', $tmp) or return (0, "Unable to create temporary configuration: $!");
    print $tfh $new;
    close($tfh);
    if (!rename($tmp, $conf)) {
        unlink($tmp);
        return (0, "Unable to install the candidate configuration: $!");
    }
    my ($test_exit, $test) = run_command('/usr/local/lsws/bin/lshttpd -t');
    if ($test_exit != 0) {
        rename($backup, $conf);
        return (0, "OpenLiteSpeed configuration validation failed.\n$test");
    }
    my ($restart_exit, $restart) = run_command('/usr/local/lsws/bin/lswsctrl restart');
    if ($restart_exit != 0) {
        rename($backup, $conf);
        run_command('/usr/local/lsws/bin/lswsctrl restart');
        return (0, "OpenLiteSpeed failed to restart. The previous configuration was restored.\n$restart");
    }
    return (1, '');
}

sub set_domain_permissions {
    my ($root) = @_;

    return (0, "Domain directory does not exist: $root")
        unless -d $root;

    my $rc = system('/usr/bin/chown', '-R', 'www-data:www-data', $root);

    if ($rc != 0) {
        my $exit = $rc >> 8;
        my $signal = $rc & 127;
        return (0, "Unable to set ownership on $root (exit=$exit signal=$signal)");
    }

    my $uid = getpwnam('www-data');
    my $gid = getgrnam('www-data');

    return (0, "Unable to resolve www-data user/group")
        unless defined $uid && defined $gid;

    my @st = stat($root);

    return (0, "Unable to verify ownership of $root")
        unless @st;

    return (0, "Ownership verification failed for $root")
        unless $st[4] == $uid && $st[5] == $gid;

    return (1, '');
}

my $content = read_config();

if ($in{'action'} eq 'add') {
    my $domain = lc($in{'domain'} || '');
    $domain =~ s/^\s+|\s+$//g;
    my $alias_prefixes = lc($in{'alias_prefixes'} || '');
    $alias_prefixes =~ s/^\s+|\s+$//g;
    my $ssl_mode = lc($in{'ssl_mode'} || 'none');
    $ssl_mode = 'none' unless $ssl_mode eq 'none' || $ssl_mode eq 'selfsigned' || $ssl_mode eq 'letsencrypt';
    my $email = $in{'ssl_email'} || '';
    $email =~ s/^\s+|\s+$//g;

    if (!valid_domain($domain)) {
        $error = 'Enter a valid domain name, for example example.com.';
    } elsif (!valid_alias_prefixes($alias_prefixes)) {
        $error = 'Aliases must contain subdomain prefixes only, separated by commas, for example xyz,account,community.';
    } elsif (grep { lc($_) eq $domain } vhost_names($content)) {
        $error = "The domain $domain is already registered.";
    } elsif ($ssl_mode eq 'letsencrypt' && !certbot_path()) {
        $error = 'Certbot is not installed. Install Certbot before selecting Let’s Encrypt.';
    } elsif ($ssl_mode eq 'letsencrypt' && (!$email || $email !~ /^[^\s\@]+\@[^\s\@]+\.[^\s\@]+$/)) {
        $error = 'A valid email address is required for Let’s Encrypt.';
    } else {
        my $aliases = build_aliases($domain, $alias_prefixes);
        my $vh_root = "$domain_base/$domain";
        my $vh_conf = "$vh_root/conf/vhconf.conf";
        my $public_html = "$vh_root/public_html";
        my $cert_root = "$config{'lsws'}/cert/$domain";
        my $dirs_ok = eval {
            make_path("$vh_root/conf", $public_html, "$vh_root/logs", "$vh_root/cgi-bin", "$public_html/.well-known/acme-challenge", "$vh_root/cachedata");
            1;
        };
        if (!$dirs_ok) {
            $error = "Unable to create the domain directories: $@";
        } elsif (-e $vh_conf) {
            $error = "The virtual host configuration already exists: $vh_conf";
        } else {
            my $vh_config = build_vhconf($domain, $aliases, 'none');
            if (!$vh_config) {
                $error = 'Unable to build the virtual host configuration from the module template.';
            } elsif (!set_domain_permissions($vh_root)) {
                $error = 'Unable to set the OpenLiteSpeed-compatible ownership on the domain directory.';
            } else {
                if ($ssl_mode eq 'selfsigned') {
                    my ($ok,$out) = generate_self_signed($domain,$aliases,$cert_root);
                    $error = $out unless $ok;
                    $vh_config = add_vhssl_block($vh_config) if $ok;
                }
                if (!$error && open(my $fh, '>', $vh_conf)) {
                    print $fh $vh_config;
                    close($fh);
                } elsif (!$error) {
                    $error = "Unable to create $vh_conf: $!";
                }
                if (!$error) {
                    my $updated = $content;
                    $updated .= "\n" unless $updated =~ /\n\z/;
                    $updated .= "\nvirtualhost $domain {\n  vhRoot $vh_root/\n  configFile $vh_conf\n}\n";
                    $updated = add_listener_maps($updated, $domain, $aliases);
                    my ($ok,$out) = apply_global_config($content,$updated);
                    if (!$ok) {
                        remove_tree($vh_root);
                        $error = $out;
                    } else {
                        $message = "Domain $domain added successfully.";
                    }
                } elsif (!$error) {
                    $error = 'Unable to create the virtual host configuration.';
                }
            }
        }
    }
}
