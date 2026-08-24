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
my $cert_root = "$config{'lsws'}/cert/$vh";
my $live_root = "/etc/letsencrypt/live/$vh";

sub ssl_read_file {
    my ($file) = @_;
    return '' if !-f $file;
    return '' if !open(my $fh, '<', $file);
    local $/;
    my $data = <$fh>;
    close($fh);
    return $data || '';
}

sub ssl_status {
    my ($file) = @_;
    return 'Missing' if !$file || !-f $file;
    my $out = &backquote_command("openssl x509 -in " . quotemeta($file) . " -noout -subject -issuer -dates 2>&1");
    return $? == 0 ? 'Valid certificate' : 'Unreadable certificate';
}

sub ssl_cert_info {
    my ($file) = @_;
    my %i;
    return %i if !$file || !-f $file;
    my $out = &backquote_command("openssl x509 -in " . quotemeta($file) . " -noout -subject -issuer -dates 2>&1");
    if ($out =~ /subject=\s*(.+)/) { $i{'subject'} = $1; }
    if ($out =~ /issuer=\s*(.+)/) { $i{'issuer'} = $1; }
    if ($out =~ /notBefore=\s*(.+)/) { $i{'from'} = $1; }
    if ($out =~ /notAfter=\s*(.+)/) { $i{'to'} = $1; }
    return %i;
}

my $fullchain = "$cert_root/fullchain.pem";
my $privkey   = "$cert_root/privkey.pem";
my %info = ssl_cert_info($fullchain);
my $exists = -f $fullchain && -f $privkey;

print <<'HTML';
<style>
.ols-ssl{max-width:1000px;margin:0 auto}.ols-ssl-hero{padding:26px 28px;border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:14px;margin-bottom:18px}.ols-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.08em;opacity:.55;font-weight:700}.ols-ssl h1{margin:6px 0;font-size:28px}.ols-muted{opacity:.62;font-size:13px}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:12px;margin-bottom:16px;overflow:hidden}.ols-card h2{font-size:16px;margin:0;padding:16px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-body{padding:18px 20px}.ols-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--border-color,rgba(128,128,128,.18));border:1px solid var(--border-color,rgba(128,128,128,.18));border-radius:9px;overflow:hidden}.ols-grid>div{padding:13px 15px;background:var(--body-bg,transparent)}.ols-label{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.06em;opacity:.52;margin-bottom:5px}.ols-value{font-size:13px;font-weight:600;word-break:break-word}.ols-badge{display:inline-block;padding:4px 9px;border-radius:999px;background:rgba(40,167,69,.13);color:#39a866;font-size:11px;font-weight:700}.ols-badge.off{background:rgba(220,53,69,.12);color:#d9534f}.ols-actions{display:flex;gap:10px;flex-wrap:wrap}.ols-btn{display:inline-block;padding:10px 15px;border-radius:8px;text-decoration:none;border:1px solid var(--border-color,rgba(128,128,128,.25));font-weight:700;font-size:12px;color:inherit}.ols-btn:hover{background:rgba(128,128,128,.09)}@media(max-width:700px){.ols-grid{grid-template-columns:1fr}}
</style>
HTML

print "<div class='ols-ssl'>";
print "<div class='ols-ssl-hero'><span class='ols-kicker'>SSL Certificate Manager</span><h1>".&html_escape($vh)."</h1><p class='ols-muted'>Manage self-signed and ACME certificates for this virtual host.</p></div>";

print "<section class='ols-card'><h2>Current Certificate</h2><div class='ols-body'><div class='ols-grid'>";
print "<div><span class='ols-label'>Status</span><span class='ols-badge".($exists?'':' off')."'>".($exists?'Installed':'Not installed')."</span></div>";
print "<div><span class='ols-label'>Type</span><span class='ols-value'>".&html_escape($exists ? 'Existing certificate' : '—')."</span></div>";
print "<div><span class='ols-label'>Issuer</span><span class='ols-value'>".&html_escape($info{'issuer'} || '—')."</span></div>";
print "<div><span class='ols-label'>Subject</span><span class='ols-value'>".&html_escape($info{'subject'} || '—')."</span></div>";
print "<div><span class='ols-label'>Valid From</span><span class='ols-value'>".&html_escape($info{'from'} || '—')."</span></div>";
print "<div><span class='ols-label'>Expires</span><span class='ols-value'>".&html_escape($info{'to'} || '—')."</span></div>";
print "<div><span class='ols-label'>Certificate</span><span class='ols-value'><code>".&html_escape($fullchain)."</code></span></div>";
print "<div><span class='ols-label'>Private Key</span><span class='ols-value'><code>".&html_escape($privkey)."</code></span></div>";
print "</div></div></section>";

print "<section class='ols-card'><h2>Certificate Actions</h2><div class='ols-body'><div class='ols-actions'>";
print "<a class='ols-btn' href='ssl.cgi?vh=".&urlize($vh)."&action=selfsigned'>Generate Self-Signed</a>";
print "<a class='ols-btn' href='ssl.cgi?vh=".&urlize($vh)."&action=letsencrypt'>Let's Encrypt</a>";
print "<a class='ols-btn' href='ssl.cgi?vh=".&urlize($vh)."&action=zerossl'>ZeroSSL</a>";
print "<a class='ols-btn' href='ssl.cgi?vh=".&urlize($vh)."&action=renew'>Renew Certificate</a>";
print "</div><p class='ols-muted' style='margin-bottom:0'>Certificate issuance and deployment will be implemented with validation and rollback before replacing the active certificate.</p></div></section>";

print "<p><a href='config.cgi?vh=".&urlize($vh)."&xnavigation=1#ssl'>← Back to SSL tab</a></p>";
print "</div>";
&ui_print_footer('');
