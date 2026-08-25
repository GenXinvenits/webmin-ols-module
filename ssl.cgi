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

sub backup_certificates {
    my $stamp = time();
    my $backup = "$cert_root/.webmin-backup-$stamp";
    return '' if !-d $cert_root && !-f $fullchain && !-f $privkey;
    mkdir($cert_root) if !-d $cert_root;
    mkdir($backup) if !-d $backup;
    for my $f ($fullchain,$privkey,$cert,$chain) {
        next unless -f $f;
        my ($name) = $f =~ m{/([^/]+)$};
        system('/bin/cp','-a',$f,"$backup/$name") == 0 or return '';
    }
    return $backup;
}

sub deploy_certificate {
    my ($source_cert,$source_key) = @_;
    return 0 unless -f $source_cert && -f $source_key;
    mkdir($cert_root) if !-d $cert_root;
    backup_certificates();
    return 0 unless system('/bin/cp','-f',$source_cert,$fullchain) == 0;
    return 0 unless system('/bin/cp','-f',$source_key,$privkey) == 0;
    system('/bin/cp','-f',$fullchain,$cert) == 0 or return 0;
    system('/bin/cp','-f',$fullchain,$chain) == 0 or return 0;
    chmod(0600,$privkey);
    chmod(0644,$cert,$chain,$fullchain);
    return 1;
}

sub validate_and_restart {
    my ($test_exit,$test_out) = run_cmd('/usr/local/lsws/bin/lshttpd -t');
    return (0, "OpenLiteSpeed configuration validation failed.\n".$test_out) if $test_exit != 0;
    my ($restart_exit,$restart_out) = run_cmd('/usr/local/lsws/bin/lswsctrl restart');
    return (0, "OpenLiteSpeed failed to restart.\n".$restart_out) if $restart_exit != 0;
    return (1, '');
}

if ($in{'action'} eq 'selfsigned') {
    my $days = 3650;
    my $key_size = 2048;
    my @domains = domains_for_vh();
    mkdir($cert_root) if !-d $cert_root;
    backup_certificates();
    my $tmp = "/tmp/webmin-ols-ssl-$$";
    mkdir($tmp);
    my $key = "$tmp/privkey.pem";
    my $crt = "$tmp/cert.pem";
    my $san = join(',', map { 'DNS:'.$_ } @domains);
    my $cn = $domains[0] || $vh;
    my $cnf = "$tmp/openssl.cnf";
    if (open(my $fh,'>',$cnf)) {
        print $fh "[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=v3\n[dn]\nCN=$cn\n[v3]\nsubjectAltName=$san\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n";
        close($fh);
        my ($e1,$o1)=run_cmd('openssl genrsa -out '.shell_quote($key).' '.$key_size);
        my ($e2,$o2)=run_cmd('openssl req -new -x509 -sha256 -key '.shell_quote($key).' -out '.shell_quote($crt).' -days '.$days.' -config '.shell_quote($cnf));
        if ($e1==0 && $e2==0) {
            if (deploy_certificate($crt,$key)) {
                my ($ok,$out)=validate_and_restart();
                if ($ok) { $message='Self-signed certificate generated, installed and OpenLiteSpeed restarted successfully.'; }
                else { $error=$out; }
            } else { $error='Unable to install the generated certificate files.'; }
        } else { $error="OpenSSL certificate generation failed.\n".($o1||$o2); }
    } else { $error='Unable to create temporary OpenSSL configuration.'; }
    unlink($key,$crt,$cnf);
    rmdir($tmp);
}

if ($in{'action'} eq 'letsencrypt_issue' || $in{'action'} eq 'renew') {
    my $email = $in{'email'} || '';
    my @domains = domains_for_vh();
    my $webroot = "$vh_root/public_html";
    my $certbot = certbot_path();
    if (!$certbot) {
        $error='Certbot is not installed. Open the SSL Dependencies page and install certbot first.';
    } elsif (!@domains) {
        $error='No valid domains were found in the virtual host configuration.';
    } elsif (!-d $webroot) {
        $error='The virtual host document root does not exist: '.$webroot;
    } elsif ($in{'action'} eq 'letsencrypt_issue' && !$email) {
        $error="An email address is required for Let's Encrypt certificate issuance.";
    } else {
        my $cert_name = $vh;
        my $cmd = shell_quote($certbot);
        if ($in{'action'} eq 'renew') {
            $cmd .= ' renew --cert-name '.shell_quote($cert_name).' --non-interactive';
        } else {
            $cmd .= ' certonly --webroot -w '.shell_quote($webroot);
            $cmd .= ' --cert-name '.shell_quote($cert_name);
            $cmd .= ' --email '.shell_quote($email);
            $cmd .= ' --agree-tos --non-interactive --keep-until-expiring';
            $cmd .= ' -d '.shell_quote($_) for @domains;
        }
        my ($e,$o)=run_cmd($cmd);
        if ($e==0) {
            my $source_root = "/etc/letsencrypt/live/$cert_name";
            my $source_cert = "$source_root/fullchain.pem";
            my $source_key = "$source_root/privkey.pem";
            if (deploy_certificate($source_cert,$source_key)) {
                my ($valid,$vo)=validate_and_restart();
                if ($valid) {
                    $message=$in{'action'} eq 'renew' ? "Let's Encrypt certificate renewed/deployed and OpenLiteSpeed restarted successfully." : "Let's Encrypt certificate issued/deployed and OpenLiteSpeed restarted successfully.";
                } else { $error=$vo; }
            } else { $error="Certbot completed successfully, but the certificate could not be deployed from $source_root."; }
        } else { $error="Let's Encrypt operation failed.\n$o"; }
    }
}

my %info=cert_info($fullchain);
my $exists=(-f $fullchain && -f $privkey);
my $type='Not installed';
if ($exists) {
    $type=(($info{'issuer'} || '') =~ /Let's Encrypt|ISRG/i) ? "Let's Encrypt" : 'Self-Signed / Other';
}
my @domains=domains_for_vh();
my $domain_text=join(', ',@domains);
my $certbot_installed=certbot_path() ? 1 : 0;
my $default_type = ($type eq "Let's Encrypt") ? 'letsencrypt' : 'selfsigned';

print <<'HTML';
<style>
.ols-ssl{max-width:1050px;margin:0 auto}.ols-ssl-hero{padding:28px 30px;border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:14px;margin-bottom:18px}.ols-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.08em;opacity:.55;font-weight:700}.ols-ssl h1{margin:6px 0;font-size:29px}.ols-muted{opacity:.62;font-size:13px}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:12px;margin-bottom:16px;overflow:hidden}.ols-card h2{font-size:16px;margin:0;padding:16px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-body{padding:18px 20px}.ols-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--border-color,rgba(128,128,128,.18));border:1px solid var(--border-color,rgba(128,128,128,.18));border-radius:9px;overflow:hidden}.ols-grid>div{padding:13px 15px;background:var(--body-bg,transparent);min-width:0}.ols-label{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.06em;opacity:.52;margin-bottom:5px}.ols-value{font-size:13px;font-weight:600;word-break:break-word}.ols-badge{display:inline-block;padding:4px 9px;border-radius:999px;background:rgba(40,167,69,.13);color:#39a866;font-size:11px;font-weight:700}.ols-badge.off{background:rgba(128,128,128,.12);color:#888}.ols-actions{display:flex;gap:10px;flex-wrap:wrap}.ols-btn{display:inline-block;padding:10px 15px;border-radius:8px;text-decoration:none;border:1px solid var(--border-color,rgba(128,128,128,.25));font-weight:700;font-size:12px;color:inherit;background:transparent;cursor:pointer}.ols-btn:hover{background:rgba(128,128,128,.09)}.ols-btn.primary{background:#3584e4;color:#fff;border-color:#3584e4}.ols-btn.primary:hover{background:#2f75c7;border-color:#2f75c7}.ols-btn:disabled{opacity:.5;cursor:not-allowed}.ols-type-box{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:10px;padding:14px}.ols-radio-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.ols-radio-option{display:block;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:9px;padding:12px;cursor:pointer}.ols-radio-option:hover{background:rgba(128,128,128,.06)}.ols-radio-option input[type="radio"]{appearance:none !important;-webkit-appearance:none !important;width:18px !important;height:18px !important;margin:0 !important;padding:0 !important;border:2px solid currentColor !important;border-radius:50% !important;background:transparent !important;opacity:1 !important;position:static !important;pointer-events:auto !important;vertical-align:middle !important;display:inline-block !important;box-sizing:border-box !important}.ols-radio-option input[type="radio"]:checked{border-color:#3584e4 !important;background:radial-gradient(circle,#3584e4 0 4px,transparent 5px) !important}.ols-radio-option input[type="radio"]:disabled{opacity:.4 !important}.lawobject{display:none !important}.ols-radio-option input[type="radio"]{display:inline-block !important;margin:0 8px 0 0 !important;vertical-align:middle !important}.ols-radio-option strong{display:inline-block;font-size:13px;vertical-align:middle;margin:0}.ols-radio-option span{display:block;margin:6px 0 0 0;font-size:11px;line-height:1.4;opacity:.62}.ols-cert-panel{margin-top:14px}.ols-form{display:grid;grid-template-columns:1fr auto;gap:14px;align-items:end}.ols-field label{display:block;font-size:11px;font-weight:700;margin-bottom:6px;opacity:.7}.ols-field input{width:100%;box-sizing:border-box;padding:10px;border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:8px;background:transparent;color:inherit}.ols-note{font-size:12px;opacity:.62}.ols-message{padding:13px 15px;border-radius:9px;margin-bottom:16px;white-space:pre-wrap}.ols-success{background:rgba(40,167,69,.1);border:1px solid rgba(40,167,69,.25)}.ols-error{background:rgba(220,53,69,.1);border:1px solid rgba(220,53,69,.25)}@media(max-width:700px){.ols-grid,.ols-radio-grid,.ols-form{grid-template-columns:1fr}}
</style>
HTML

print "<div class='ols-ssl'>";
print "<div class='ols-ssl-hero'><span class='ols-kicker'>SSL Certificate Manager</span><h1>".&html_escape($vh)."</h1><p class='ols-muted'>Manage the SSL certificate for this virtual host.</p></div>";
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
print "</div></div></section>";

print "<section class='ols-card'><h2>Certificate Type</h2><div class='ols-body'><form method='post' action='ssl.cgi' id='ssl-cert-form'><input type='hidden' name='vh' value='".&quote_escape($vh)."'><input type='hidden' name='action' id='ssl-action' value='".($default_type eq 'letsencrypt' ? 'letsencrypt_issue' : 'selfsigned')."'><div class='ols-type-box'><div class='ols-radio-grid'>";
print "<label class='ols-radio-option'><input type='radio' name='cert_type' value='selfsigned'".($default_type eq 'selfsigned'?' checked':'')."><strong>Self-Signed</strong><span>Generate a 2048-bit RSA certificate valid for 10 years using the virtual host domains as SANs.</span></label>";
print "<label class='ols-radio-option'><input type='radio' name='cert_type' value='letsencrypt'".($default_type eq 'letsencrypt'?' checked':'')."><strong>Let's Encrypt</strong><span>Use Certbot to obtain a trusted certificate from Let's Encrypt for all configured domains.</span></label>";
print "</div><div id='selfsigned-panel' class='ols-cert-panel'><p class='ols-note'>The self-signed certificate is useful for internal sites, testing and environments where a public CA certificate is not required.</p></div>";
print "<div id='letsencrypt-panel' class='ols-cert-panel' style='display:none'>";
if (!$certbot_installed) {
    print "<p class='ols-note'>Certbot is not installed. Install it from the SSL Dependencies page before requesting a Let's Encrypt certificate.</p><div class='ols-actions'><a class='ols-btn' href='ssl-dependencies.cgi?vh=".&urlize($vh)."'>Open SSL Dependencies</a></div>";
} else {
    print "<div class='ols-form'><div class='ols-field'><label for='ssl-email'>Account Email</label><input id='ssl-email' type='email' name='email' placeholder='you@example.com'></div></div><p class='ols-note'>Let's Encrypt will validate all domains configured for this virtual host through the website document root.</p>";
}
print "</div></div><div class='ols-actions' style='margin-top:14px'><button class='ols-btn primary' id='ssl-submit' type='submit'>".($default_type eq 'letsencrypt' ? "Issue Let's Encrypt Certificate" : 'Generate / Replace Self-Signed Certificate')."</button></div></form></div></section>";

print "<section class='ols-card'><h2>Renewal</h2><div class='ols-body'><p class='ols-muted'>Renew the existing Let's Encrypt certificate when it is due for renewal, then deploy the renewed files to OpenLiteSpeed.</p><form method='post' action='ssl.cgi'><input type='hidden' name='vh' value='".&quote_escape($vh)."'><input type='hidden' name='action' value='renew'><div class='ols-actions'><button class='ols-btn primary' type='submit'".($certbot_installed?'':' disabled').">Renew Let's Encrypt Certificate</button><a class='ols-btn' href='ssl-dependencies.cgi?vh=".&urlize($vh)."'>SSL Dependencies</a></div></form></div></section>";
print "<p><a href='config.cgi?vh=".&urlize($vh)."&xnavigation=1#ssl'>← Back to SSL tab</a></p>";
print "</div>";

print <<'HTML';
<script>
(function(){
  var form=document.getElementById('ssl-cert-form');
  if(!form)return;
  var action=document.getElementById('ssl-action');
  var selfPanel=document.getElementById('selfsigned-panel');
  var lePanel=document.getElementById('letsencrypt-panel');
  var submit=document.getElementById('ssl-submit');
  var email=document.getElementById('ssl-email');
  function sync(){
    var selected=form.querySelector('input[name="cert_type"]:checked');
    var le=selected && selected.value==='letsencrypt';
    selfPanel.style.display=le?'none':'block';
    lePanel.style.display=le?'block':'none';
    action.value=le?'letsencrypt_issue':'selfsigned';
    submit.textContent=le?"Issue Let's Encrypt Certificate":"Generate / Replace Self-Signed Certificate";
    if(email)email.required=le;
  }
  form.querySelectorAll('input[name="cert_type"]').forEach(function(r){r.addEventListener('change',sync);});
  sync();
})();
</script>
HTML

&ui_print_footer('');
