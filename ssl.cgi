#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'SSL Certificate Manager', '');
&ReadParse();

my $vh = $in{'vh'} || '';
$vh =~ s/[^A-Za-z0-9._-]//g;

if (!$vh) {
    print "<h2>SSL Certificate Manager</h2><p>No virtual host was specified.</p><a href='index.cgi'>Back to OpenLiteSpeed</a>";
    &ui_print_footer('index.cgi');
    exit;
}

my $vh_root = "$config{'lsws'}/domains/$vh";
my $vh_conf = "$vh_root/conf/vhconf.conf";
my $cert_root = "$config{'lsws'}/cert/$vh";
my $fullchain = "$cert_root/fullchain.pem";
my $privkey = "$cert_root/privkey.pem";
my $cert = "$cert_root/cert.pem";
my $chain = "$cert_root/chain.pem";
my $message = '';
my $error = '';

sub shell_quote {
    my ($s) = @_;
    $s = '' unless defined $s;
    $s =~ s/'/'\\''/g;
    return "'$s'";
}

sub run_cmd {
    my ($cmd) = @_;
    my $out = &backquote_command($cmd . ' 2>&1');
    my $exit = $? >> 8;
    return ($exit, $out);
}

sub certbot_path {
    my ($e,$o) = run_cmd('command -v certbot');
    return '' if $e != 0;
    $o =~ s/\s+$//;
    return $o if -x $o;
    return '';
}

sub cert_info {
    my ($file) = @_;
    my %i;
    return %i if !-f $file;
    my ($exit, $out) = run_cmd('openssl x509 -in '.shell_quote($file).' -noout -subject -issuer -dates -ext subjectAltName');
    return %i if $exit != 0;
    $i{'subject'} = $1 if $out =~ /^subject=\s*(.+)$/m;
    $i{'issuer'} = $1 if $out =~ /^issuer=\s*(.+)$/m;
    $i{'from'} = $1 if $out =~ /^notBefore=\s*(.+)$/m;
    $i{'to'} = $1 if $out =~ /^notAfter=\s*(.+)$/m;
    if ($out =~ /X509v3 Subject Alternative Name:\s*\n\s*(.+)/s) {
        $i{'san'} = $1;
        $i{'san'} =~ s/\s+/ /g;
    }
    return %i;
}

sub get_vh_value {
    my ($name, $text) = @_;
    return '' unless defined $text;
    return $1 if $text =~ /^\s*\Q$name\E\s+(.+?)\s*$/m;
    return '';
}

sub resolve_value {
    my ($v) = @_;
    return '' unless defined $v;
    $v =~ s/\$VH_NAME/$vh/g;
    $v =~ s/\$VH_ROOT/$vh_root/g;
    $v =~ s/\$SERVER_ROOT/$config{'lsws'}/g;
    return $v;
}

sub domains_for_vh {
    my @domains;
    return @domains if !-f $vh_conf;
    my $c = &read_file_contents($vh_conf);
    for my $field ('vhDomain','vhAliases') {
        my $v = resolve_value(get_vh_value($field,$c));
        next if !$v;
        for my $d (split(/\s+/, $v)) {
            $d =~ s/^https?:\/\///;
            $d =~ s/\/$//;
            push @domains, $d if $d =~ /^[A-Za-z0-9][A-Za-z0-9.-]*$/ && $d !~ /^\$/;
        }
    }
    push @domains, $vh if !@domains;
    my %seen;
    return grep {!$seen{$_}++} @domains;
}

# /usr/local/lsws/cert is a symlink to /etc/letsencrypt/live.
# The live files themselves are Certbot-style symlinks to archive.
# Nothing is copied into a second certificate directory.
sub deploy_certificate {
    my ($source_cert,$source_key) = @_;
    return (0, "Certificate source does not exist: $source_cert") unless -f $source_cert;
    return (0, "Private key source does not exist: $source_key") unless -f $source_key;

    my ($ce,$co) = run_cmd('openssl x509 -in '.shell_quote($source_cert).' -noout');
    return (0, "Unable to read certificate $source_cert.\n$co") if $ce != 0;

    my ($ke,$ko) = run_cmd('openssl pkey -in '.shell_quote($source_key).' -noout');
    return (0, "Unable to read private key $source_key.\n$ko") if $ke != 0;

    return (0, "Certificate path is not a symlink: $source_cert") unless -l $source_cert;
    return (0, "Private key path is not a symlink: $source_key") unless -l $source_key;
    return (0, "OpenLiteSpeed certificate path is missing: $fullchain") unless -e $fullchain;
    return (0, "OpenLiteSpeed private key path is missing: $privkey") unless -e $privkey;
    return (1, '');
}

sub validate_and_restart {
    my ($test_exit,$test_out) = run_cmd('/usr/local/lsws/bin/lshttpd -t');
    return (0, "OpenLiteSpeed configuration validation failed.\n".$test_out) if $test_exit != 0;
    my ($restart_exit,$restart_out) = run_cmd('/usr/local/lsws/bin/lswsctrl restart');
    return (0, "OpenLiteSpeed failed to restart.\n".$restart_out) if $restart_exit != 0;
    return (1, '');
}

sub lineage_version {
    my ($archive) = @_;
    my $version = 1;
    if (-d $archive) {
        opendir(my $dh, $archive);
        my $max = 0;
        while (my $f = readdir($dh)) {
            if ($f =~ /^cert(\d+)\.pem$/) {
                $max = $1 if $1 > $max;
            }
        }
        closedir($dh);
        $version = $max + 1 if $max;
    }
    return $version;
}

sub write_certbot_readme {
    my ($live_dir) = @_;
    my $readme = "$live_dir/README";
    if (open(my $fh, '>', $readme)) {
        print $fh <<'EOF';
This directory contains your keys and certificates.

`privkey.pem`  : the private key for your certificate.
`fullchain.pem`: the certificate file used in most server software.
`chain.pem`    : the certificate chain file.
`cert.pem`     : the certificate file.

WARNING: DO NOT MOVE OR RENAME THESE FILES!
         The certificate manager expects these files to remain in this location.
EOF
        close($fh);
        chmod(0644, $readme);
    }
}

sub install_lineage {
    my ($archive_dir,$live_dir,$version,$cert_pem,$chain_pem,$key_pem) = @_;
    my $archive_key = "$archive_dir/privkey${version}.pem";
    my $archive_cert = "$archive_dir/cert${version}.pem";
    my $archive_chain = "$archive_dir/chain${version}.pem";
    my $archive_fullchain = "$archive_dir/fullchain${version}.pem";
    my $tmp_dir = "/tmp/webmin-ols-lineage-$$";
    mkdir($tmp_dir);

    my $tmp_key = "$tmp_dir/privkey.pem";
    my $tmp_cert = "$tmp_dir/cert.pem";
    my $tmp_chain = "$tmp_dir/chain.pem";
    my $tmp_fullchain = "$tmp_dir/fullchain.pem";

    my $ok = 1;
    $ok &&= open(my $kf, '>', $tmp_key);
    if ($ok) { print $kf $key_pem; close($kf); }
    $ok &&= open(my $cf, '>', $tmp_cert);
    if ($ok) { print $cf $cert_pem; close($cf); }
    $chain_pem = $cert_pem if !defined($chain_pem) || $chain_pem eq '';
    $ok &&= open(my $chf, '>', $tmp_chain);
    if ($ok) { print $chf $chain_pem; close($chf); }
    $ok &&= open(my $ff, '>', $tmp_fullchain);
    if ($ok) { print $ff $cert_pem; print $ff "\n" unless $cert_pem =~ /\n\s*$/; print $ff $chain_pem; close($ff); }

    if ($ok) {
        chmod(0600,$tmp_key);
        chmod(0644,$tmp_cert,$tmp_chain,$tmp_fullchain);
        my ($ce,$co)=run_cmd('openssl x509 -in '.shell_quote($tmp_cert).' -noout');
        my ($ke,$ko)=run_cmd('openssl pkey -in '.shell_quote($tmp_key).' -noout');
        if ($ce != 0 || $ke != 0) {
            $error="Custom certificate validation failed.\n".($co||$ko);
            $ok=0;
        }
        if ($ok) {
            my ($match_e,$match_o)=run_cmd('openssl x509 -in '.shell_quote($tmp_cert).' -pubkey -noout | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum');
            my ($key_e,$key_o)=run_cmd('openssl pkey -in '.shell_quote($tmp_key).' -pubout -outform DER 2>/dev/null | sha256sum');
            if ($match_e != 0 || $key_e != 0 || $match_o !~ /^([0-9a-f]+)/ || $key_o !~ /^([0-9a-f]+)/ || $1 ne $key_o =~ /^([0-9a-f]+)/ ? $1 : '') {
                my ($a_e,$a_o)=run_cmd('openssl x509 -in '.shell_quote($tmp_cert).' -pubkey -noout | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum');
                my ($b_e,$b_o)=run_cmd('openssl pkey -in '.shell_quote($tmp_key).' -pubout -outform DER 2>/dev/null | sha256sum');
                my ($a)=($a_o =~ /^([0-9a-f]+)/); my ($b)=($b_o =~ /^([0-9a-f]+)/);
                if (!$a || !$b || $a ne $b) {
                    $error='The custom private key does not match the supplied certificate.';
                    $ok=0;
                }
            }
        }
    } else {
        $error='Unable to prepare the custom certificate files.';
    }

    if ($ok) {
        $ok = (system('/bin/mv','-f',$tmp_key,$archive_key)==0 &&
               system('/bin/mv','-f',$tmp_cert,$archive_cert)==0 &&
               system('/bin/mv','-f',$tmp_chain,$archive_chain)==0 &&
               system('/bin/mv','-f',$tmp_fullchain,$archive_fullchain)==0);
        if (!$ok) { $error='Unable to store the custom certificate lineage in the archive.'; }
    }

    if ($ok) {
        chmod(0600,$archive_key);
        chmod(0644,$archive_cert,$archive_chain,$archive_fullchain);
        unlink("$live_dir/privkey.pem","$live_dir/cert.pem","$live_dir/chain.pem","$live_dir/fullchain.pem");
        $ok &&= symlink("../../archive/$vh/privkey${version}.pem", "$live_dir/privkey.pem");
        $ok &&= symlink("../../archive/$vh/cert${version}.pem", "$live_dir/cert.pem");
        $ok &&= symlink("../../archive/$vh/chain${version}.pem", "$live_dir/chain.pem");
        $ok &&= symlink("../../archive/$vh/fullchain${version}.pem", "$live_dir/fullchain.pem");
        write_certbot_readme($live_dir) if $ok;
        $error='Unable to create the live certificate symlinks.' if !$ok && !$error;
    }

    unlink($tmp_key,$tmp_cert,$tmp_chain,$tmp_fullchain);
    rmdir($tmp_dir);
    return $ok;
}

sub remove_lineage {
    my $base_dir = '/etc/letsencrypt';
    my $archive_dir = "$base_dir/archive/$vh";
    my $live_dir = "$base_dir/live/$vh";
    return (1,'') unless -d $archive_dir || -d $live_dir;

    my $stamp = time();
    my $backup_root = "/tmp/webmin-ols-remove-$vh-$stamp-$$";
    mkdir($backup_root) or return (0,"Unable to create temporary SSL removal backup: $!");

    my $archive_backup = "$backup_root/archive";
    my $live_backup = "$backup_root/live";
    my $moved_archive = 0;
    my $moved_live = 0;

    if (-d $archive_dir) {
        if (rename($archive_dir,$archive_backup)) { $moved_archive=1; }
        else { rmdir($backup_root); return (0,"Unable to move the certificate archive out of the way: $!"); }
    }
    if (-d $live_dir) {
        if (rename($live_dir,$live_backup)) { $moved_live=1; }
        else {
            rename($archive_backup,$archive_dir) if $moved_archive;
            rmdir($backup_root);
            return (0,"Unable to move the live certificate directory out of the way: $!");
        }
    }

    my ($valid,$out)=validate_and_restart();
    if (!$valid) {
        rename($live_backup,$live_dir) if $moved_live;
        rename($archive_backup,$archive_dir) if $moved_archive;
        rmdir($backup_root);
        return (0,"SSL removal was rolled back because OpenLiteSpeed could not validate/restart.\n$out");
    }

    system('/bin/rm','-rf',$backup_root);
    return (1,'');
}

if ($in{'action'} eq 'selfsigned') {
    my $days = 3650;
    my $key_size = 2048;
    my @domains = domains_for_vh();
    my $base_dir = '/etc/letsencrypt';
    my $archive_dir = "$base_dir/archive/$vh";
    my $live_dir = "$base_dir/live/$vh";
    mkdir($base_dir) if !-d $base_dir;
    mkdir("$base_dir/archive") if !-d "$base_dir/archive";
    mkdir("$base_dir/live") if !-d "$base_dir/live";
    mkdir($archive_dir) if !-d $archive_dir;
    mkdir($live_dir) if !-d $live_dir;

    my $version = lineage_version($archive_dir);
    my $tmp = "/tmp/webmin-ols-ssl-$$";
    mkdir($tmp);
    my $key = "$tmp/privkey.pem";
    my $crt = "$tmp/cert.pem";
    my $cnf = "$tmp/openssl.cnf";
    my $san = join(',', map { 'DNS:'.$_ } @domains);
    my $cn = $domains[0] || $vh;

    if (open(my $fh,'>',$cnf)) {
        print $fh "[ req ]\ndefault_bits = $key_size\nprompt = no\ndefault_md = sha256\ndistinguished_name = dn\nx509_extensions = req_ext\n\n[ dn ]\nCN = $cn\n\n[ req_ext ]\nsubjectAltName = $san\nkeyUsage = digitalSignature,keyEncipherment\nextendedKeyUsage = serverAuth\n";
        close($fh);
        my ($e1,$o1)=run_cmd('openssl genrsa -out '.shell_quote($key).' '.$key_size);
        my ($e2,$o2)=run_cmd('openssl req -new -x509 -sha256 -key '.shell_quote($key).' -out '.shell_quote($crt).' -days '.$days.' -config '.shell_quote($cnf));
        if ($e1==0 && $e2==0) {
            if (system('/bin/cp','-f',$key,"$archive_dir/privkey${version}.pem")==0 &&
                system('/bin/cp','-f',$crt,"$archive_dir/cert${version}.pem")==0 &&
                system('/bin/cp','-f',$crt,"$archive_dir/chain${version}.pem")==0 &&
                system('/bin/cp','-f',$crt,"$archive_dir/fullchain${version}.pem")==0) {
                chmod(0600,"$archive_dir/privkey${version}.pem");
                chmod(0644,"$archive_dir/cert${version}.pem","$archive_dir/chain${version}.pem","$archive_dir/fullchain${version}.pem");
                unlink("$live_dir/privkey.pem","$live_dir/cert.pem","$live_dir/chain.pem","$live_dir/fullchain.pem");
                symlink("../../archive/$vh/privkey${version}.pem", "$live_dir/privkey.pem");
                symlink("../../archive/$vh/cert${version}.pem", "$live_dir/cert.pem");
                symlink("../../archive/$vh/chain${version}.pem", "$live_dir/chain.pem");
                symlink("../../archive/$vh/fullchain${version}.pem", "$live_dir/fullchain.pem");
                write_certbot_readme($live_dir);
                my ($de,$do)=deploy_certificate($live_dir.'/fullchain.pem',$live_dir.'/privkey.pem');
                if ($de) {
                    my ($ok,$out)=validate_and_restart();
                    $ok ? ($message="Self-signed certificate generated as version $version, Certbot-style lineage updated and OpenLiteSpeed restarted successfully.") : ($error=$out);
                } else { $error="Certificate lineage was created, but the certificate could not be deployed to OpenLiteSpeed.\n$do"; }
            } else { $error='Unable to store the generated certificate lineage in /etc/letsencrypt/archive/'.$vh.'.'; }
        } else { $error="OpenSSL certificate generation failed.\n".($o1||$o2); }
    } else { $error='Unable to create temporary OpenSSL configuration.'; }
    unlink($key,$crt,$cnf); rmdir($tmp);
}

if ($in{'action'} eq 'custom_install') {
    my $custom_cert = $in{'custom_cert'} || '';
    my $custom_key = $in{'custom_key'} || '';
    my $custom_chain = $in{'custom_chain'} || '';
    $custom_cert =~ s/^\s+//; $custom_cert =~ s/\s+$//;
    $custom_key =~ s/^\s+//; $custom_key =~ s/\s+$//;
    $custom_chain =~ s/^\s+//; $custom_chain =~ s/\s+$//;

    if (!$custom_cert || !$custom_key) {
        $error='Both the certificate and private key are required.';
    } elsif ($custom_cert !~ /-----BEGIN CERTIFICATE-----/ || $custom_cert !~ /-----END CERTIFICATE-----/) {
        $error='The certificate does not appear to be a valid PEM certificate.';
    } elsif ($custom_key !~ /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/ || $custom_key !~ /-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/) {
        $error='The private key does not appear to be a supported PEM private key.';
    } elsif ($custom_chain && $custom_chain !~ /-----BEGIN CERTIFICATE-----/) {
        $error='The certificate chain does not appear to be valid PEM certificate data.';
    } else {
        my $base_dir='/etc/letsencrypt';
        my $archive_dir="$base_dir/archive/$vh";
        my $live_dir="$base_dir/live/$vh";
        mkdir($base_dir) if !-d $base_dir;
        mkdir("$base_dir/archive") if !-d "$base_dir/archive";
        mkdir("$base_dir/live") if !-d "$base_dir/live";
        mkdir($archive_dir) if !-d $archive_dir;
        mkdir($live_dir) if !-d $live_dir;
        my $version=lineage_version($archive_dir);
        if (install_lineage($archive_dir,$live_dir,$version,$custom_cert,$custom_chain,$custom_key)) {
            my ($de,$do)=deploy_certificate($live_dir.'/fullchain.pem',$live_dir.'/privkey.pem');
            if ($de) {
                my ($ok,$out)=validate_and_restart();
                if ($ok) { $message="Custom SSL certificate installed as version $version, lineage updated and OpenLiteSpeed restarted successfully."; }
                else { $error=$out; }
            } else { $error="Custom certificate was stored, but it could not be deployed to OpenLiteSpeed.\n$do"; }
        }
    }
}

if ($in{'action'} eq 'remove_ssl') {
    my ($ok,$out)=remove_lineage();
    if ($ok) {
        $message='Installed SSL certificate lineage was removed successfully and OpenLiteSpeed restarted.';
    } else {
        $error=$out;
    }
}

if ($in{'action'} eq 'letsencrypt_issue' || $in{'action'} eq 'renew') {
    my $email = $in{'email'} || '';
    my @domains = domains_for_vh();
    my $webroot = "$vh_root/public_html";
    my $certbot = certbot_path();
    if (!$certbot) { $error='Certbot is not installed. Open the SSL Dependencies page and install certbot first.'; }
    elsif (!@domains) { $error='No valid domains were found in the virtual host configuration.'; }
    elsif (!-d $webroot) { $error='The virtual host document root does not exist: '.$webroot; }
    elsif ($in{'action'} eq 'letsencrypt_issue' && !$email) { $error="An email address is required for Let's Encrypt certificate issuance."; }
    else {
        my $cert_name=$vh; my $cmd=shell_quote($certbot);
        if ($in{'action'} eq 'renew') { $cmd .= ' renew --cert-name '.shell_quote($cert_name).' --non-interactive'; }
        else {
            $cmd .= ' certonly --webroot -w '.shell_quote($webroot).' --cert-name '.shell_quote($cert_name).' --email '.shell_quote($email).' --agree-tos --non-interactive --keep-until-expiring';
            $cmd .= ' -d '.shell_quote($_) for @domains;
        }
        my ($e,$o)=run_cmd($cmd);
        if ($e==0) {
            my $source_root="/etc/letsencrypt/live/$cert_name";
            my ($de,$do)=deploy_certificate("$source_root/fullchain.pem","$source_root/privkey.pem");
            if ($de) {
                my ($valid,$vo)=validate_and_restart();
                $valid ? ($message=$in{'action'} eq 'renew' ? "Let's Encrypt certificate renewed and OpenLiteSpeed restarted successfully." : "Let's Encrypt certificate issued and OpenLiteSpeed restarted successfully.") : ($error=$vo);
            } else { $error="Certbot completed successfully, but the certificate lineage could not be used by OpenLiteSpeed.\n$do"; }
        } else { $error="Let's Encrypt operation failed.\n$o"; }
    }
}

my %info=cert_info($fullchain);
my $exists=(-f $fullchain && -f $privkey);
my $type='Not installed';
if ($exists) { $type=(($info{'issuer'} || '') =~ /Let's Encrypt|ISRG/i) ? "Let's Encrypt" : 'Self-Signed / Other'; }
my @domains=domains_for_vh();
my $domain_text=join(', ',@domains);
my $certbot_installed=certbot_path() ? 1 : 0;
my ($openssl_exit,$openssl_output)=run_cmd('command -v openssl');
my $openssl_installed=($openssl_exit == 0 && $openssl_output =~ /\S/) ? 1 : 0;
my $default_type=($type eq "Let's Encrypt") ? 'letsencrypt' : 'selfsigned';

print <<'HTML';
<style>
.ols-ssl{max-width:1050px;margin:0 auto}.ols-ssl-hero{padding:28px 30px;border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:14px;margin-bottom:18px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:32px;align-items:center}.ols-ssl-hero-main{min-width:0}.ols-ssl-hero-deps{min-width:260px;padding-left:28px;border-left:1px solid var(--border-color,rgba(128,128,128,.18))}.ols-ssl-hero-deps-title{font-size:12px;font-weight:700;margin-bottom:8px}.ols-ssl-hero-deps-list{margin-bottom:10px}.ols-deps-item{display:flex;align-items:center;gap:8px;font-size:12px;margin:5px 0}.ols-deps-dot{width:7px;height:7px;border-radius:50%;background:#39a866;display:inline-block}.ols-deps-item.off{opacity:.72}.ols-deps-item.off .ols-deps-dot{background:#888}.ols-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.08em;opacity:.55;font-weight:700}.ols-ssl h1{margin:6px 0;font-size:29px}.ols-muted{opacity:.62;font-size:13px}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:12px;margin-bottom:16px;overflow:hidden}.ols-card h2{font-size:16px;margin:0;padding:16px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-body{padding:18px 20px}.ols-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--border-color,rgba(128,128,128,.18));border:1px solid var(--border-color,rgba(128,128,128,.18));border-radius:9px;overflow:hidden}.ols-grid>div{padding:13px 15px;background:var(--body-bg,transparent);min-width:0}.ols-label{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.06em;opacity:.52;margin-bottom:5px}.ols-value{font-size:13px;font-weight:600;word-break:break-word}.ols-badge{display:inline-block;padding:4px 9px;border-radius:999px;background:rgba(40,167,69,.13);color:#39a866;font-size:11px;font-weight:700}.ols-badge.off{background:rgba(128,128,128,.12);color:#888}.ols-actions{display:flex;gap:10px;flex-wrap:wrap}.ols-btn{display:inline-block;padding:10px 15px;border-radius:8px;text-decoration:none;border:1px solid var(--border-color,rgba(128,128,128,.25));font-weight:700;font-size:12px;color:inherit;background:transparent;cursor:pointer}.ols-btn:hover{background:rgba(128,128,128,.09)}.ols-btn.primary{background:#3584e4;color:#fff;border-color:#3584e4}.ols-btn.primary:hover{background:#2f75c7;border-color:#2f75c7}.ols-btn.danger{color:#d9534f;border-color:rgba(217,83,79,.35)}.ols-btn.danger:hover{background:rgba(217,83,79,.08)}.ols-type-box{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:10px;padding:14px}.ols-radio-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.ols-radio-option{display:block;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:9px;padding:12px;cursor:pointer}.ols-radio-option:hover{background:rgba(128,128,128,.06)}.ols-radio-option input[type="radio"]{appearance:none!important;-webkit-appearance:none!important;width:18px!important;height:18px!important;margin:0 10px 0 0!important;padding:0!important;border:2px solid currentColor!important;border-radius:50%!important;background:transparent!important;opacity:1!important;position:static!important;pointer-events:auto!important;vertical-align:middle!important;display:inline-block!important;box-sizing:border-box!important}.ols-radio-option input[type="radio"]:checked{border-color:#3584e4!important;background:radial-gradient(circle,#3584e4 0 4px,transparent 5px)!important}.ols-radio-option strong{display:inline-block;font-size:13px;vertical-align:middle}.ols-radio-option span{display:block;margin:6px 0 0;font-size:11px;line-height:1.4;opacity:.62}.ols-cert-panel{margin-top:14px}.ols-form{display:grid;grid-template-columns:1fr auto;gap:14px;align-items:end}.ols-field label{display:block;font-size:11px;font-weight:700;margin-bottom:6px;opacity:.7}.ols-field input{width:100%;box-sizing:border-box;padding:10px;border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:8px;background:transparent;color:inherit}.ols-field textarea{width:100%;box-sizing:border-box;min-height:180px;padding:10px;border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:8px;background:#111827;color:#e5e7eb;font:12px/1.45 monospace}.ols-custom-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.ols-custom-full{grid-column:1/-1}.ols-note{font-size:12px;opacity:.62}.ols-message{padding:13px 15px;border-radius:9px;margin-bottom:16px;white-space:pre-wrap}.ols-success{background:rgba(40,167,69,.1);border:1px solid rgba(40,167,69,.25)}.ols-error{background:rgba(220,53,69,.1);border:1px solid rgba(220,53,69,.25)}
@media(max-width:800px){.ols-ssl-hero{grid-template-columns:1fr;gap:18px}.ols-ssl-hero-deps{min-width:0;padding-left:0;padding-top:18px;border-left:0;border-top:1px solid var(--border-color,rgba(128,128,128,.18))}.ols-grid,.ols-radio-grid,.ols-custom-grid,.ols-form{grid-template-columns:1fr}.ols-custom-full{grid-column:auto}}
</style>
HTML

print "<div class='ols-ssl'>";
print "<div class='ols-ssl-hero'><div class='ols-ssl-hero-main'><span class='ols-kicker'>SSL Certificate Manager</span><h1>".&html_escape($vh)."</h1><p class='ols-muted'>Manage the SSL certificate for this virtual host.</p></div><div class='ols-ssl-hero-deps'><div class='ols-ssl-hero-deps-title'>SSL Dependencies</div><div class='ols-ssl-hero-deps-list'><div class='ols-deps-item".($openssl_installed?'':' off')."'><span class='ols-deps-dot'></span><span>".($openssl_installed?'OpenSSL is installed':'OpenSSL is not installed')."</span></div><div class='ols-deps-item".($certbot_installed?'':' off')."'><span class='ols-deps-dot'></span><span>".($certbot_installed?'Certbot is installed':'Certbot is not installed')."</span></div></div><a class='ols-btn' href='ssl-dependencies.cgi?vh=".&urlize($vh)."'>Manage Dependencies →</a></div></div>";
print "<div class='ols-message ols-success'>".&html_escape($message)."</div>" if $message;
print "<div class='ols-message ols-error'>".&html_escape($error)."</div>" if $error;
print "<section class='ols-card'><h2>Current Certificate</h2><div class='ols-body'><div class='ols-grid'>";
print "<div><span class='ols-label'>Status</span><span class='ols-badge".($exists?'':' off')."'>".($exists?'Installed':'Not installed')."</span></div>";
print "<div><span class='ols-label'>Certificate Type</span><span class='ols-value'>".&html_escape($type)."</span></div>";
print "<div><span class='ols-label'>Domains / SAN</span><span class='ols-value'>".&html_escape($domain_text)."</span></div>";
print "<div><span class='ols-label'>Issuer</span><span class='ols-value'>".&html_escape($info{'issuer'}||'—')."</span></div>";
print "<div><span class='ols-label'>Valid From</span><span class='ols-value'>".&html_escape($info{'from'}||'—')."</span></div>";
print "<div><span class='ols-label'>Expires</span><span class='ols-value'>".&html_escape($info{'to'}||'—')."</span></div>";
print "<div><span class='ols-label'>Certificate</span><span class='ols-value'><code>".&html_escape($fullchain)."</code></span></div>";
print "<div><span class='ols-label'>Private Key</span><span class='ols-value'><code>".&html_escape($privkey)."</code></span></div>";
print "</div><div class='ols-actions' style='margin-top:14px'>";
if ($exists) { print "<form method='post' action='ssl.cgi' onsubmit=\"return confirm('Remove the installed SSL certificate and its archive/live lineage for this virtual host?')\"><input type='hidden' name='vh' value='".&quote_escape($vh)."'><input type='hidden' name='action' value='remove_ssl'><button class='ols-btn danger' type='submit'>Remove Installed SSL</button></form>"; }
print "</div></div></section>";

print "<section class='ols-card'><h2>Certificate Type</h2><div class='ols-body'><form method='post' action='ssl.cgi' id='ssl-cert-form'><input type='hidden' name='vh' value='".&quote_escape($vh)."'><input type='hidden' name='action' id='ssl-action' value='".($default_type eq 'letsencrypt' ? 'letsencrypt_issue' : 'selfsigned')."'><div class='ols-type-box'><div class='ols-radio-grid'>";
print "<label class='ols-radio-option'><input type='radio' name='cert_type' value='selfsigned'".($default_type eq 'selfsigned'?' checked':'')."><strong>Self-Signed</strong><span>Generate a 2048-bit RSA certificate valid for 10 years using the virtual host domains as SANs.</span></label>";
print "<label class='ols-radio-option'><input type='radio' name='cert_type' value='letsencrypt'".($default_type eq 'letsencrypt'?' checked':'')."><strong>Let's Encrypt</strong><span>Use Certbot to obtain a trusted certificate from Let's Encrypt for all configured domains.</span></label>";
print "<label class='ols-radio-option'><input type='radio' name='cert_type' value='custom'><strong>Custom SSL</strong><span>Install an existing certificate and private key from another certificate authority or provider.</span></label>";
print "</div><div id='selfsigned-panel' class='ols-cert-panel'><p class='ols-note'>The self-signed certificate is useful for internal sites, testing and environments where a public CA certificate is not required. Certificates are stored using the same archive/live lineage layout used by Certbot.</p></div>";
print "<div id='letsencrypt-panel' class='ols-cert-panel' style='display:none'>";
if (!$certbot_installed) { print "<p class='ols-note'>Certbot is not installed. Use the SSL Dependencies button above to install certbot before requesting a Let's Encrypt certificate.</p>"; }
else { print "<div class='ols-form'><div class='ols-field'><label for='ssl-email'>Account Email</label><input id='ssl-email' type='email' name='email' placeholder='you@example.com'></div></div><p class='ols-note'>Let's Encrypt will validate all domains configured for this virtual host through the website document root.</p>"; }
print "</div>";
print "<div id='custom-panel' class='ols-cert-panel' style='display:none'><p class='ols-note'>Paste the PEM certificate and private key below. The optional chain should contain the intermediate CA certificate(s). The module validates the certificate and key match, stores them in the archive lineage, and updates the live symlinks without copying certificates into a second directory.</p><div class='ols-custom-grid'><div class='ols-field ols-custom-full'><label for='custom-cert'>Certificate (PEM)</label><textarea id='custom-cert' name='custom_cert' placeholder='-----BEGIN CERTIFICATE-----'></textarea></div><div class='ols-field'><label for='custom-chain'>Intermediate Chain (PEM, optional)</label><textarea id='custom-chain' name='custom_chain' placeholder='-----BEGIN CERTIFICATE-----'></textarea></div><div class='ols-field'><label for='custom-key'>Private Key (PEM)</label><textarea id='custom-key' name='custom_key' placeholder='-----BEGIN PRIVATE KEY-----'></textarea></div></div></div>";
print "</div><div class='ols-actions' style='margin-top:14px'><button class='ols-btn primary' id='ssl-submit' type='submit'>".($default_type eq 'letsencrypt' ? "Issue Let's Encrypt Certificate" : 'Generate / Replace Self-Signed Certificate')."</button>";
if ($certbot_installed) { print "<button class='ols-btn primary' id='ssl-renew' type='submit' name='action' value='renew' formnovalidate>Renew Let's Encrypt Certificate</button>"; }
print "</div></form></div></section>";

print "<p><a href='config.cgi?vh=".&urlize($vh)."&xnavigation=1#ssl'>← Back to SSL tab</a></p></div>";

print <<'HTML';
<script>
(function(){
  var form=document.getElementById('ssl-cert-form'); if(!form)return;
  var action=document.getElementById('ssl-action'), selfPanel=document.getElementById('selfsigned-panel'), lePanel=document.getElementById('letsencrypt-panel'), customPanel=document.getElementById('custom-panel'), submit=document.getElementById('ssl-submit'), renew=document.getElementById('ssl-renew'), email=document.getElementById('ssl-email');
  var cert=document.getElementById('custom-cert'), key=document.getElementById('custom-key');
  function sync(){
    var selected=form.querySelector('input[name="cert_type"]:checked'); var type=selected?selected.value:'selfsigned';
    selfPanel.style.display=type==='selfsigned'?'block':'none'; lePanel.style.display=type==='letsencrypt'?'block':'none'; customPanel.style.display=type==='custom'?'block':'none';
    if(renew)renew.style.display=type==='letsencrypt'?'inline-block':'none';
    action.value=type==='letsencrypt'?'letsencrypt_issue':(type==='custom'?'custom_install':'selfsigned');
    submit.textContent=type==='letsencrypt'?"Issue Let's Encrypt Certificate":(type==='custom'?'Install Custom SSL Certificate':'Generate / Replace Self-Signed Certificate');
    if(email)email.required=type==='letsencrypt';
    if(cert)cert.required=type==='custom'; if(key)key.required=type==='custom';
  }
  form.querySelectorAll('input[name="cert_type"]').forEach(function(r){r.addEventListener('change',sync);}); sync();
})();
</script>
HTML

&ui_print_footer('');
