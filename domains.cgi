#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'Domain Management', '');
&ReadParse();

use File::Path qw(make_path);
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

    # Install the candidate temporarily so lshttpd validates the actual file we changed.
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
    # OpenLiteSpeed refuses vhost roots owned by UID 0/GID 0 or nobody (65534).
    my ($ec,$out) = run_command('/usr/bin/chown -R www-data:www-data ' . quote_shell_command($root));
    return ($ec == 0, $out);
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
                    my $block = "\nvirtualhost $domain {\n    vhRoot $vh_root/\n    configFile $vh_conf\n    allowSymbolLink 1\n    enableScript 1\n    restrained 1\n}\n";
                    my $new = add_listener_maps($content . $block, $domain, $aliases);
                    my ($ok,$out) = apply_global_config($content,$new);
                    if (!$ok) {
                        unlink($vh_conf);
                        $error = $out;
                    } elsif ($ssl_mode eq 'letsencrypt') {
                        my $certbot = certbot_path();
                        my $cmd = quote_shell_command($certbot) . ' certonly --webroot -w ' . quote_shell_command($public_html) . ' --cert-name ' . quote_shell_command($domain) . ' --non-interactive --agree-tos --email ' . quote_shell_command($email) . ' --keep-until-expiring';
                        $cmd .= ' -d ' . quote_shell_command($domain);
                        $cmd .= ' -d ' . quote_shell_command($_) for split(/\s+/, $aliases || '');
                        my ($cert_exit,$out_cert) = run_command($cmd);
                        my $issued = "/etc/letsencrypt/live/$domain/fullchain.pem";
                        my $issued_key = "/etc/letsencrypt/live/$domain/privkey.pem";
                        if ($cert_exit == 0 && install_certificate($issued,$issued_key,$cert_root)) {
                            my $old_vh = read_file_contents($vh_conf);
                            my $ssl_vh = add_vhssl_block($old_vh);
                            if (open(my $wh,'>',$vh_conf)) { print $wh $ssl_vh; close($wh); }
                            my ($ssl_ok,$ssl_out) = apply_global_config($new,$new);
                            if ($ssl_ok) {
                                $message = "Domain $domain was added successfully with a trusted Let's Encrypt certificate.";
                            } else {
                                open(my $rh,'>',$vh_conf); print $rh remove_vhssl_block($old_vh); close($rh);
                                run_command('/usr/local/lsws/bin/lswsctrl restart');
                                $message = "Domain $domain was added successfully, but SSL could not be activated.";
                                $error = $ssl_out;
                            }
                        } else {
                            $message = "Domain $domain was added successfully without SSL.";
                            $error = "Let's Encrypt certificate issuance failed. The domain remains available without SSL.\n$out_cert";
                        }
                    } elsif ($ssl_mode eq 'selfsigned') {
                        $message = "Domain $domain was added successfully with a self-signed certificate.";
                    } else {
                        $message = "Domain $domain was added successfully without SSL.";
                    }
                }
            }
        }
    }
}
elsif ($in{'action'} eq 'remove') {
    my $domain = $in{'domain'} || '';
    $domain =~ s/[^A-Za-z0-9._-]//g;
    if (!$domain || !grep { $_ eq $domain } vhost_names($content)) {
        $error = 'The selected domain is not registered.';
    } else {
        my ($new,$found) = remove_vhost_block($content,$domain);
        $new = remove_listener_maps($new,$domain);
        if ($found) {
            my ($ok,$out) = apply_global_config($content,$new);
            if ($ok) {
                my $vh_conf = "$domain_base/$domain/conf/vhconf.conf";
                unlink($vh_conf) if -f $vh_conf;
                $message = "Domain $domain was removed successfully. Website files were left untouched.";
            } else {
                $error = $out;
            }
        } else {
            $error = 'Unable to locate the virtual host configuration block.';
        }
    }
}

$content = read_config();
my @domains = vhost_names($content);

print <<'HTML';
<style>
.ols-domains{max-width:1050px;margin:0 auto}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:12px;margin-bottom:16px;overflow:hidden}.ols-card h2{font-size:16px;margin:0;padding:16px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-body{padding:18px 20px}.ols-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.ols-field label{display:block;font-size:11px;font-weight:700;margin-bottom:6px;opacity:.7}.ols-field input{width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:4px;background:transparent;color:inherit}.ols-note,.ols-field-help{font-size:11px;line-height:1.45;opacity:.58}.ols-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:14px}.ols-btn{display:inline-block;padding:8px 13px;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;color:inherit;background:transparent;cursor:pointer}.ols-list{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:8px;overflow:hidden}.ols-row{display:grid;grid-template-columns:minmax(220px,1fr) minmax(250px,1fr) 100px;gap:12px;align-items:center;padding:11px 13px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-row:last-child{border-bottom:0}.ols-head{font-size:10px;text-transform:uppercase;letter-spacing:.05em;font-weight:700;opacity:.58}.ols-domain{font-weight:700}.ols-danger{color:#d9534f}.ols-add-highlight{border-color:rgba(53,132,228,.38);background:linear-gradient(180deg,rgba(53,132,228,.08),rgba(53,132,228,.025));box-shadow:0 2px 10px rgba(53,132,228,.06)}.ols-add-highlight h2{background:rgba(53,132,228,.07);border-bottom-color:rgba(53,132,228,.18)}.ols-add-intro{display:flex;align-items:flex-start;gap:12px;margin-bottom:18px}.ols-add-icon{width:34px;height:34px;flex:0 0 34px;border-radius:9px;display:flex;align-items:center;justify-content:center;background:rgba(53,132,228,.13);color:#3584e4;font-size:20px}.ols-add-copy strong{display:block;font-size:13px;margin-bottom:3px}.ols-add-copy span{display:block;font-size:12px;line-height:1.5;opacity:.68}.ols-alias-input{display:flex;align-items:center;border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:4px;overflow:hidden}.ols-alias-input input{border:0!important;border-radius:0!important;min-width:0}.ols-alias-suffix{padding:0 10px;font-size:12px;opacity:.62;white-space:nowrap}.ols-notification,.ols-error-notification{display:flex;align-items:flex-start;gap:10px;padding:12px 15px;margin:0 0 16px;border-radius:8px;font-size:13px;font-weight:600}.ols-notification{border:1px solid rgba(40,167,69,.28);background:rgba(40,167,69,.10)}.ols-notification:before{content:'✓';display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:rgba(40,167,69,.18);color:#35a854}.ols-error-notification{border:1px solid rgba(220,53,69,.28);background:rgba(220,53,69,.10)}.ols-error-notification:before{content:'!';display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:rgba(220,53,69,.18);color:#d9534f}.ols-ssl-options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}.ols-ssl-option{border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:8px;padding:11px 12px}.ols-ssl-option label{display:block;font-size:12px;font-weight:700;cursor:pointer}.ols-ssl-option input{width:auto;margin-right:7px}.ols-ssl-option span{display:block;margin:5px 0 0 22px;font-size:11px;line-height:1.4;opacity:.6}.ols-ssl-email{margin-top:10px;display:none}.ols-ssl-email.visible{display:block}
</style>
HTML

print "<div class='ols-domains'>";
print "<div class='ols-notification'>".&html_escape($message)."</div>" if $message;
print "<div class='ols-error-notification'>".&html_escape($error)."</div>" if $error;
print "<section class='ols-card ols-add-highlight'><h2>Add Domain</h2><div class='ols-body'><div class='ols-add-intro'><div class='ols-add-icon'>+</div><div class='ols-add-copy'><strong>Register a new website with OpenLiteSpeed</strong><span>Creates the virtual host, public_html, logs, CGI directory, cache directory and listener mappings automatically.</span></div></div><form method='post' action='domains.cgi'><input type='hidden' name='action' value='add'><div class='ols-grid'><div class='ols-field'><label for='ols-domain'>Domain</label><input id='ols-domain' name='domain' type='text' placeholder='example.com' required><span class='ols-field-help'>Enter the primary domain, without http:// or https://.</span></div><div class='ols-field'><label for='ols-alias-prefixes'>Aliases / Subdomains</label><div class='ols-alias-input'><input id='ols-alias-prefixes' name='alias_prefixes' type='text' placeholder='xyz,account,community' autocomplete='off'><span class='ols-alias-suffix' id='ols-alias-suffix'>.example.com</span></div><span class='ols-field-help'>Enter prefixes separated by commas. For example xyz,account,community becomes xyz.example.com, account.example.com and community.example.com. www is always added automatically.</span></div></div><div class='ols-field' style='margin-top:16px'><label>SSL Certificate</label><div class='ols-ssl-options'><div class='ols-ssl-option'><label><input type='radio' name='ssl_mode' value='none' checked>No SSL</label><span>Create the domain without HTTPS certificate configuration.</span></div><div class='ols-ssl-option'><label><input type='radio' name='ssl_mode' value='selfsigned'>Self-Signed</label><span>Generate a local certificate for testing or internal use.</span></div><div class='ols-ssl-option'><label><input type='radio' name='ssl_mode' value='letsencrypt'>Let's Encrypt</label><span>Use installed Certbot to issue a trusted public certificate.</span></div></div><div class='ols-ssl-email' id='ols-ssl-email'><label for='ols-ssl-email-input'>Certificate email</label><input id='ols-ssl-email-input' name='ssl_email' type='email' placeholder='you@example.com'><span class='ols-field-help'>Required only for Let's Encrypt.</span></div></div><div class='ols-actions'><button class='ols-btn' type='submit'>Add Domain</button><a class='ols-btn' href='index.cgi'>Back to Websites</a></div></form></div></section>";
print "<section class='ols-card'><h2>Registered Domains</h2><div class='ols-body'><p class='ols-note'>Removing a domain unregisters its OpenLiteSpeed configuration and listener mappings. Website files remain untouched.</p><div class='ols-list'><div class='ols-row ols-head'><div>Domain</div><div>Virtual Host</div><div>Action</div></div>";
if (!@domains) { print "<div class='ols-body ols-note'>No domains registered.</div>"; }
else { for my $d (@domains) { print "<div class='ols-row'><div class='ols-domain'>".&html_escape($d)."</div><div>".&html_escape("$domain_base/$d")."</div><div><form method='post' action='domains.cgi' onsubmit=\"return confirm('Remove $d from OpenLiteSpeed? Website files will be preserved.');\"><input type='hidden' name='action' value='remove'><input type='hidden' name='domain' value='".&quote_escape($d)."'><button class='ols-btn ols-danger' type='submit'>Remove</button></form></div></div>"; } }
print "</div></div></section></div>";

print <<'HTML';
<script>
(function(){
 var domain=document.getElementById('ols-domain'),suffix=document.getElementById('ols-alias-suffix'),emailBox=document.getElementById('ols-ssl-email');
 function updateSuffix(){if(!domain||!suffix)return;var v=domain.value.trim().replace(/^https?:\\/\\//i,'').replace(/\\/.*$/,'');suffix.textContent=v?'.'+v:'.example.com';}
 function updateSsl(){if(!emailBox)return;var r=document.querySelector('input[name="ssl_mode"]:checked');emailBox.className='ols-ssl-email'+(r&&r.value==='letsencrypt'?' visible':'');}
 if(domain)domain.addEventListener('input',updateSuffix);updateSuffix();
 document.querySelectorAll('input[name="ssl_mode"]').forEach(function(x){x.addEventListener('change',updateSsl)});updateSsl();
})();
</script>
HTML
&ui_print_footer('index.cgi');
