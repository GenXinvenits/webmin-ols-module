#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'SSL Dependencies', '');
&ReadParse();

sub esc { return &html_escape(defined $_[0] ? $_[0] : ''); }
sub run_cmd {
    my ($cmd) = @_;
    my $out = &backquote_command($cmd . ' 2>&1');
    my $exit = $? >> 8;
    return ($exit, $out);
}
sub command_exists {
    my ($cmd) = @_;
    my ($e, $o) = run_cmd('command -v ' . quotemeta($cmd));
    return ($e == 0 && $o =~ /\S/);
}
sub distro_info {
    my %d;
    if (open(my $fh, '<', '/etc/os-release')) {
        while (my $line = <$fh>) {
            if ($line =~ /^([A-Z_]+)=(.*)$/) {
                my ($k,$v)=($1,$2); $v =~ s/^"|"$//g; $d{$k}=$v;
            }
        }
        close($fh);
    }
    return %d;
}
sub package_manager {
    return 'apt' if command_exists('apt-get');
    return 'dnf' if command_exists('dnf');
    return 'yum' if command_exists('yum');
    return 'pacman' if command_exists('pacman');
    return 'zypper' if command_exists('zypper');
    return '';
}
sub pkg_installed {
    my ($pkg,$pm) = @_;
    return 0 unless $pm;
    my ($e,$o);
    if ($pm eq 'apt') { ($e,$o)=run_cmd('dpkg-query -W -f=${Status} '.quotemeta($pkg)); return !$e && $o =~ /install ok installed/; }
    if ($pm eq 'dnf' || $pm eq 'yum') { ($e,$o)=run_cmd($pm.' list installed '.quotemeta($pkg)); return !$e; }
    if ($pm eq 'pacman') { ($e,$o)=run_cmd('pacman -Q '.quotemeta($pkg)); return !$e; }
    if ($pm eq 'zypper') { ($e,$o)=run_cmd('rpm -q '.quotemeta($pkg)); return !$e; }
    return 0;
}
sub install_packages {
    my ($pm,@pkgs)=@_;
    my $list=join(' ',map {quotemeta($_)} @pkgs);
    return (1,'No supported package manager was found.') unless $pm;
    my $cmd;
    if ($pm eq 'apt') { $cmd="DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y $list"; }
    elsif ($pm eq 'dnf') { $cmd="dnf install -y $list"; }
    elsif ($pm eq 'yum') { $cmd="yum install -y $list"; }
    elsif ($pm eq 'pacman') { $cmd="pacman --noconfirm -S $list"; }
    elsif ($pm eq 'zypper') { $cmd="zypper --non-interactive install $list"; }
    else { return (1,'Unsupported package manager.'); }
    return run_cmd($cmd);
}

my %d=distro_info();
my $pm=package_manager();
my $message=''; my $error='';

if ($in{'action'} eq 'install_packages') {
    my @needed;
    my @candidates = ($pm eq 'apt' ? ('openssl','curl','socat') : ('openssl','curl','socat'));
    push @needed, grep {!pkg_installed($_,$pm)} @candidates;
    if (@needed) {
        my ($e,$o)=install_packages($pm,@needed);
        $e ? ($error="Package installation failed.\n$o") : ($message='Required SSL packages installed successfully.');
    } else { $message='All required system packages are already installed.'; }
}

if ($in{'action'} eq 'install_acme') {
    if (!command_exists('curl')) { $error='curl is required before acme.sh can be installed.'; }
    else {
        my $home=$ENV{'HOME'} || '/root';
        my ($e,$o)=run_cmd("export HOME=".quotemeta($home)."; curl -fsSL https://get.acme.sh | sh");
        if (!$e) { $message='acme.sh installed successfully. Refresh this page to verify it.'; }
        else { $error="acme.sh installation failed.\n$o"; }
    }
}

my $acme='';
for my $candidate ('/root/.acme.sh/acme.sh', ($ENV{'HOME'}||'').'/ .acme.sh/acme.sh') {
    $candidate =~ s{/ }{/}g;
    if (-x $candidate) { $acme=$candidate; last; }
}
$acme ||= 'Not installed';

print <<'HTML';
<style>
.ols-deps{max-width:900px;margin:0 auto}.ols-hero{padding:28px 30px;border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:14px;margin-bottom:18px}.ols-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.08em;opacity:.55;font-weight:700}.ols-hero h1{margin:6px 0;font-size:28px}.ols-muted{opacity:.62;font-size:13px}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:12px;margin-bottom:16px;overflow:hidden}.ols-card h2{font-size:16px;margin:0;padding:16px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-body{padding:18px 20px}.ols-row{display:grid;grid-template-columns:1fr auto;gap:16px;padding:14px 2px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.13))}.ols-row:last-child{border-bottom:0}.ols-name{font-weight:700}.ols-desc{font-size:12px;opacity:.6;margin-top:4px}.ols-ok{color:#35a854;font-weight:700}.ols-missing{color:#d9534f;font-weight:700}.ols-btn{display:inline-block;padding:10px 15px;border-radius:8px;text-decoration:none;border:1px solid var(--border-color,rgba(128,128,128,.25));font-weight:700;font-size:12px;color:inherit}.ols-btn.primary{background:#3584e4;color:#fff;border-color:#3584e4}.ols-message{padding:13px 15px;border-radius:9px;margin-bottom:16px;white-space:pre-wrap}.ols-success{background:rgba(40,167,69,.1);border:1px solid rgba(40,167,69,.25)}.ols-error{background:rgba(220,53,69,.1);border:1px solid rgba(220,53,69,.25)}code{word-break:break-all}@media(max-width:650px){.ols-row{grid-template-columns:1fr}}
</style>
HTML

my @pkg_rows;
for my $pkg ('openssl','curl','socat') {
    my $ok=pkg_installed($pkg,$pm);
    push @pkg_rows, [$pkg,$ok];
}

print "<div class='ols-deps'>";
print "<div class='ols-hero'><span class='ols-kicker'>SSL System Requirements</span><h1>Dependencies</h1><p class='ols-muted'>The module checks the operating system before enabling certificate operations. Missing packages can be installed from the system package manager.</p></div>";
print "<div class='ols-message ols-success'>".esc($message)."</div>" if $message;
print "<div class='ols-message ols-error'>".esc($error)."</div>" if $error;

print "<section class='ols-card'><h2>System packages</h2><div class='ols-body'>";
for my $r (@pkg_rows) {
    print "<div class='ols-row'><div><div class='ols-name'>".esc($r->[0])."</div><div class='ols-desc'>Required for certificate generation, inspection or ACME support.</div></div><div class='".($r->[1]?'ols-ok':'ols-missing')."'>".($r->[1]?'Installed':'Missing')."</div></div>";
}
print "</div></section>";

my $missing=grep {!$_->[1]} @pkg_rows;
print "<section class='ols-card'><h2>ACME client</h2><div class='ols-body'>";
print "<div class='ols-row'><div><div class='ols-name'>acme.sh</div><div class='ols-desc'>Used for Let's Encrypt and ZeroSSL certificate issuance and renewal.</div></div><div class='".($acme eq 'Not installed'?'ols-missing':'ols-ok')."'>".esc($acme eq 'Not installed'?'Not installed':'Installed')."</div></div>";
print "<p class='ols-muted'>Let's Encrypt and ZeroSSL do not require separate distro packages when acme.sh is used as the ACME client.</p>";
if ($missing) { print "<a class='ols-btn primary' href='ssl-dependencies.cgi?action=install_packages'>Install missing packages</a> "; }
if ($acme eq 'Not installed') { print "<a class='ols-btn primary' href='ssl-dependencies.cgi?action=install_acme'>Install acme.sh</a>"; }
print "</div></section>";

print "<section class='ols-card'><h2>Detected system</h2><div class='ols-body'><div class='ols-row'><div class='ols-name'>Distribution</div><div>".esc($d{'PRETTY_NAME'} || $d{'NAME'} || 'Unknown')."</div></div><div class='ols-row'><div class='ols-name'>Package manager</div><div>".esc($pm || 'Not detected')."</div></div></div></section>";
print "<p><a href='javascript:history.back()'>← Back</a></p></div>";
&ui_print_footer('');
