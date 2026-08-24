#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'SSL Certificate Manager', '');
&ReadParse();

my $vh = $in{'vh'} || '';
$vh =~ s/[^A-Za-z0-9._-]//g;

if (!$vh) {
    print "<h2>SSL Certificate Manager</h2><p>No virtual host was specified.</p><a href='index.cgi'>Back to OpenLiteSpeed</a>";
    &ui_print_footer('index.cgi'); exit;
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
    if ($out =~ /X509v3 Subject Alternative Name:\s*\n\s*(.+)/s) { $i{'san'} = $1; $i{'san'} =~ s/\s+/ /g; }
    return %i;
}

sub get_vh_value {
    my ($name, $text) = @_;
    return '' unless defined $text;
    if ($text =~ /^\s*\Q$name\E\s+(.+?)\s*$/m) { return $1; }
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
            $d =~ s/^https?:\/\///; $d =~ s/\/$//;
            push @domains, $d if $d =~ /^[A-Za-z0-9][A-Za-z0-9.-]*$/ && $d !~ /^\$/;
        }
    }
    push @domains, $vh if !@domains;
    my %seen; return grep {!$seen{$_}++} @domains;
}

sub backup_certificates {
    my $stamp = time();
    my $backup = "$cert_root/.webmin-backup-$stamp";
    return '' if !-d $cert_root && !-f $fullchain && !-f $privkey;
    mkdir($backup) if !-d $backup;
    for my $f ($fullchain,$privkey,$cert,$chain) {
        next unless -f $f;
        my ($name) = $f =~ m{/([^/]+)$};
        system('/bin/cp','-a',$f,"$backup/$name") == 0 or return '';
    }
    return $backup;
}

sub validate_and_restart {
    my ($test_exit,$test_out) = run_cmd('/usr/local/lsws/bin/lshttpd -t');
    return (0, 'OpenLiteSpeed configuration validation failed.\n'.$test_out) if $test_exit != 0;
    my ($restart_exit,$restart_out) = run_cmd('/usr/local/lsws/bin/lswsctrl restart');
    return (0, 'OpenLiteSpeed failed to restart.\n'.$restart_out) if $restart_exit != 0;
    return (1, '');
}

if ($in{'action'} eq 'selfsigned') {
    my $days = 3650;
    my $key_size = 2048;
    my @domains = domains_for_vh();
    mkdir($cert_root) if !-d $cert_root;
    my $backup = backup_certificates();
    my $tmp = "/tmp/webmin-ols-ssl-$$";
    mkdir($tmp);
    my $key = "$tmp/privkey.pem"; my $crt = "$tmp/cert.pem";
    my $san = join(',', map { 'DNS:'.$_ } @domains);
    my $cn = $domains[0];
    my $cnf = "$tmp/openssl.cnf";
    if (open(my $fh,'>',$cnf)) {
        print $fh "[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=v3\n[dn]\nCN=$cn\n[v3]\nsubjectAltName=$san\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n";
        close($fh);
        my ($e1,$o1)=run_cmd('openssl genrsa -out '.shell_quote($key).' '.$key_size);
        my ($e2,$o2)=run_cmd('openssl req -new -x509 -sha256 -key '.shell_quote($key).' -out '.shell_quote($crt).' -days '.$days.' -config '.shell_quote($cnf));
        if ($e1==0 && $e2==0) {
            if (system('/bin/cp','-f',$key,$privkey)==0 && system('/bin/cp','-f',$crt,$cert)==0) {
                system('/bin/cp','-f',$crt,$chain); system('/bin/cp','-f',$crt,$fullchain);
                chmod(0600,$privkey); chmod(0644,$cert,$chain,$fullchain);
                my ($ok,$out)=validate_and_restart();
                if ($ok) { $message='Self-signed certificate generated, installed and OpenLiteSpeed restarted successfully.'; }
                else { $error=$out; }
            } else { $error='Unable to install the generated certificate files.'; }
        } else { $error='OpenSSL certificate generation failed.\n'.($o1||$o2); }
    } else { $error='Unable to create temporary OpenSSL configuration.'; }
    unlink($key,$crt,$cnf); rmdir($tmp);
}

if ($in{'action'} eq 'acme_issue' || $in{'action'} eq 'renew') {
    my $ca = $in{'ca'} || 'letsencrypt';
    $ca = 'zerossl' if $ca eq 'zerossl';
    my $email = $in{'email'} || '';
    my @domains = domains_for_vh();
    my $webroot = "$vh_root/public_html";
    my ($find_exit,$find_out)=run_cmd('command -v acme.sh');
    my $acme = $find_exit == 0 ? $find_out : '/root/.acme.sh/acme.sh';
    $acme =~ s/\s+$//;
    if (!-x $acme) {
        $error='acme.sh is not installed. Install acme.sh first, then return here.';
    } elsif (!-d $webroot) {
        $error='The virtual host document root does not exist: '.$webroot;
    } else {
        my $cmd = shell_quote($acme);
        if ($ca eq 'zerossl') {
            if ($email) { $cmd .= ' --register-account --server zerossl --accountemail '.shell_quote($email); }
            $cmd .= ' --server zerossl';
        } else { $cmd .= ' --server letsencrypt'; }
        if ($in{'action'} eq 'renew') {
            $cmd .= ' --renew -d '.shell_quote($domains[0]);
        } else {
            $cmd .= ' --issue --webroot '.shell_quote($webroot);
            $cmd .= ' -d '.shell_quote($_) for @domains;
        }
        my ($e,$o)=run_cmd($cmd);
        if ($e==0) {
            my $source="$ENV{'HOME'}/.acme.sh/$domains[0]";
            $source="/root/.acme.sh/$domains[0]" if !-d $source;
            my $issued="$source/fullchain.cer"; my $issued_key="$source/$domains[0].key";
            if (-f $issued && -f $issued_key) {
                mkdir($cert_root) if !-d $cert_root;
                my $backup=backup_certificates();
                my $ok=system('/bin/cp','-f',$issued,$fullchain)==0 && system('/bin/cp','-f',$issued_key,$privkey)==0;
                if ($ok) {
                    system('/bin/cp','-f',$fullchain,$cert); system('/bin/cp','-f',$fullchain,$chain);
                    chmod(0600,$privkey); chmod(0644,$cert,$chain,$fullchain);
                    my ($valid,$vo)=validate_and_restart();
                    if ($valid) { $message=ucfirst($ca).' certificate issued/deployed and OpenLiteSpeed restarted successfully.'; }
                    else { $error=$vo; }
                } else { $error='ACME succeeded, but the certificate could not be deployed.'; }
            } else { $error='ACME reported success, but the expected certificate files were not found.\n'.$o; }
        } else { $error='ACME operation failed.\n'.$o; }
    }
}

my $info_file=$fullchain;
my %info=cert_info($info_file);
my $exists=(-f $fullchain && -f $privkey);
my $type='Not installed';
if ($exists) { $type = (($info{'issuer'}||'') =~ /Let's Encrypt|ISRG/i) ? "Let's Encrypt" : (($info{'issuer'}||'') =~ /ZeroSSL|GoGetSSL/i ? 'ZeroSSL' : (($info{'subject'}||'') =~ /CN=/ ? 'Certificate' : 'Certificate')); }
my @domains=domains_for_vh();
my $domain_text=join(', ',@domains);

print <<'HTML';
<style>
.ols-ssl{max-width:1050px;margin:0 auto}.ols-ssl-hero{padding:28px 30px;border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:14px;margin-bottom:18px}.ols-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.08em;opacity:.55;font-weight:700}.ols-ssl h1{margin:6px 0;font-size:29px}.ols-muted{opacity:.62;font-size:13px}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:12px;margin-bottom:16px;overflow:hidden}.ols-card h2{font-size:16px;margin:0;padding:16px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-body{padding:18px 20px}.ols-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--border-color,rgba(128,128,128,.18));border:1px solid var(--border-color,rgba(128,128,128,.18));border-radius:9px;overflow:hidden}.ols-grid>div{padding:13px 15px;background:var(--body-bg,transparent);min-width:0}.ols-label{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.06em;opacity:.52;margin-bottom:5px}.ols-value{font-size:13px;font-weight:600;word-break:break-word}.ols-badge{display:inline-block;padding:4px 9px;border-radius:999px;background:rgba(40,167,69,.13);color:#39a866;font-size:11px;font-weight:700}.ols-badge.off{background:rgba(128,128,128,.12);color:#888}.ols-actions{display:flex;gap:10px;flex-wrap:wrap}.ols-btn{display:inline-block;padding:10px 15px;border-radius:8px;text-decoration:none;border:1px solid var(--border-color,rgba(128,128,128,.25));font-weight:700;font-size:12px;color:inherit}.ols-btn:hover{background:rgba(128,128,128,.09)}.ols-form{display:grid;grid-template-columns:1fr 1fr;gap:14px}.ols-field label{display:block;font-size:11px;font-weight:700;margin-bottom:6px;opacity:.7}.ols-field input,.ols-field select{width:100%;box-sizing:border-box;padding:10px;border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:8px;background:transparent;color:inherit}.ols-wide{grid-column:1/-1}.ols-note{font-size:12px;opacity:.62}.ols-message{padding:13px 15px;border-radius:9px;margin-bottom:16px;white-space:pre-wrap}.ols-success{background:rgba(40,167,69,.1);border:1px solid rgba(40,167,69,.25)}.ols-error{background:rgba(220,53,69,.1);border:1px solid rgba(220,53,69,.25)}@media(max-width:700px){.ols-grid,.ols-form{grid-template-columns:1fr}.ols-wide{grid-column:auto}}
</style>
HTML

print "<div class='ols-ssl'>";
print "<div class='ols-ssl-hero'><span class='ols-kicker'>SSL Certificate Manager</span><h1>".&html_escape($vh)."</h1><p class='ols-muted'>Manage self-signed certificates and ACME certificates for this virtual host.</p></div>";
if ($message) { print "<div class='ols-message ols-success'>".&html_escape($message)."</div>"; }
if ($error) { print "<div class='ols-message ols-error'>".&html_escape($error)."</div>"; }
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

print "<section class='ols-card'><h2>Self-Signed Certificate</h2><div class='ols-body'><p class='ols-muted'>Generate a 2048-bit RSA SHA-256 self-signed certificate valid for 10 years using the virtual host domain and aliases as SANs.</p><div class='ols-actions'><a class='ols-btn' href='ssl.cgi?vh=".&urlize($vh)."&action=selfsigned'>Generate / Replace Self-Signed Certificate</a></div></div></section>";

print "<section class='ols-card'><h2>ACME Certificate</h2><div class='ols-body'><form method='post' action='ssl.cgi'><input type='hidden' name='vh' value='".&quote_escape($vh)."'><input type='hidden' name='action' value='acme_issue'><div class='ols-form'><div class='ols-field'><label>Certificate Authority</label><select name='ca'><option value='letsencrypt'>Let's Encrypt</option><option value='zerossl'>ZeroSSL</option></select></div><div class='ols-field'><label>Account Email</label><input type='email' name='email' placeholder='you@example.com'></div><div class='ols-wide'><span class='ols-note'>Domains will be taken automatically from the virtual host configuration and validated through the website document root.</span></div><div class='ols-wide'><button class='ols-btn' type='submit'>Issue ACME Certificate</button></div></div></form></div></section>";

print "<section class='ols-card'><h2>Renewal</h2><div class='ols-body'><p class='ols-muted'>Renew the existing ACME certificate using its configured certificate authority.</p><form method='post' action='ssl.cgi'><input type='hidden' name='vh' value='".&quote_escape($vh)."'><input type='hidden' name='action' value='renew'><div class='ols-form'><div class='ols-field'><label>Certificate Authority</label><select name='ca'><option value='letsencrypt'>Let's Encrypt</option><option value='zerossl'>ZeroSSL</option></select></div><div class='ols-field'><label>Account Email (ZeroSSL when required)</label><input type='email' name='email'></div><div class='ols-wide'><button class='ols-btn' type='submit'>Renew Certificate Now</button></div></div></form></div></section>";

print "<p><a href='config.cgi?vh=".&urlize($vh)."&xnavigation=1#ssl'>← Back to SSL tab</a></p>";
print "</div>";
&ui_print_footer('');
