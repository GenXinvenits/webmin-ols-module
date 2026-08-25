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
sub distro_info {
    my %d;
    if (open(my $fh,'<','/etc/os-release')) {
        while (my $line=<$fh>) {
            if ($line =~ /^([A-Z_]+)=(.*)$/) {
                my ($k,$v)=($1,$2); $v =~ s/^"|"$//g; $d{$k}=$v;
            }
        }
        close($fh);
    }
    return %d;
}
sub package_manager {
    return 'apt' if -x '/usr/bin/dpkg' && -x '/usr/bin/apt-get';
    return 'dnf' if -x '/usr/bin/dnf';
    return 'yum' if -x '/usr/bin/yum';
    return 'pacman' if -x '/usr/bin/pacman';
    return 'zypper' if -x '/usr/bin/zypper';
    return '';
}
sub pkg_installed {
    my ($pkg,$pm)=@_;
    if ($pm eq 'apt') {
        return 0 unless -x '/usr/bin/dpkg-query';
        my ($e,$o)=run_cmd("/usr/bin/dpkg-query -W -f='\${Status}' " . $pkg);
        return 1 if !$e && $o =~ /install ok installed/;
        ($e,$o)=run_cmd("/usr/bin/dpkg -s " . $pkg);
        return 1 if !$e && $o =~ /^Status:\s*install ok installed$/m;
        return 0;
    }
    if ($pm eq 'dnf' || $pm eq 'yum') {
        my ($e,$o)=run_cmd("/usr/bin/$pm list installed " . $pkg);
        return !$e;
    }
    if ($pm eq 'pacman') {
        my ($e,$o)=run_cmd('/usr/bin/pacman -Q '.$pkg);
        return !$e;
    }
    if ($pm eq 'zypper') {
        my ($e,$o)=run_cmd('/usr/bin/rpm -q '.$pkg);
        return !$e;
    }
    return 0;
}
sub executable_present {
    my ($pkg)=@_;
    return 1 if $pkg eq 'openssl' && -x '/usr/bin/openssl';
    return 1 if $pkg eq 'certbot' && -x '/usr/bin/certbot';
    return 0;
}
sub dependency_installed {
    my ($pkg,$pm)=@_;
    return 1 if executable_present($pkg);
    return pkg_installed($pkg,$pm);
}
sub package_command {
    my ($pm,$action,@pkgs)=@_;
    return '' unless $pm && @pkgs;
    my $list=join(' ',@pkgs);
    if ($pm eq 'apt') {
        return "DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get update && DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get $action -y $list";
    }
    if ($pm eq 'dnf') { return "/usr/bin/dnf $action -y $list"; }
    if ($pm eq 'yum') { return "/usr/bin/yum $action -y $list"; }
    if ($pm eq 'pacman') {
        return $action eq 'remove' ? "/usr/bin/pacman --noconfirm -Rns $list" : "/usr/bin/pacman --noconfirm -S $list";
    }
    if ($pm eq 'zypper') {
        return $action eq 'remove' ? "/usr/bin/zypper --non-interactive remove $list" : "/usr/bin/zypper --non-interactive install $list";
    }
    return '';
}
sub install_packages {
    my ($pm,@pkgs)=@_;
    my $cmd=package_command($pm,'install',@pkgs);
    return (1,'No supported package manager was found.') unless $cmd;
    return run_cmd($cmd);
}
sub reinstall_packages {
    my ($pm,@pkgs)=@_;
    return (1,'No supported package manager was found.') unless $pm && @pkgs;
    my $list=join(' ',@pkgs);
    my $cmd;
    if ($pm eq 'apt') {
        $cmd="DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get update && DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get install --reinstall -y $list";
    } elsif ($pm eq 'dnf') {
        $cmd="/usr/bin/dnf reinstall -y $list";
    } elsif ($pm eq 'yum') {
        $cmd="/usr/bin/yum reinstall -y $list";
    } elsif ($pm eq 'pacman') {
        $cmd="/usr/bin/pacman --noconfirm -S $list";
    } elsif ($pm eq 'zypper') {
        $cmd="/usr/bin/zypper --non-interactive install --force-resolution $list";
    } else {
        return (1,'Unsupported package manager.');
    }
    return run_cmd($cmd);
}
sub remove_packages {
    my ($pm,@pkgs)=@_;
    my $cmd=package_command($pm,'remove',@pkgs);
    return (1,'No supported package manager was found.') unless $cmd;
    return run_cmd($cmd);
}

my %d=distro_info();
my $pm=package_manager();
my $message='';
my $error='';
my $vh=$in{'vh'} || '';
$vh =~ s/[^A-Za-z0-9._-]//g;
my $vh_query=$vh ? '&vh='.&urlize($vh) : '';
my $back=$vh ? "ssl.cgi?vh=".&urlize($vh) : "index.cgi";

if ($in{'action'} eq 'install_packages') {
    my @needed=grep {!dependency_installed($_,$pm)} qw(openssl certbot);
    if (@needed) {
        my ($e,$o)=install_packages($pm,@needed);
        $e ? ($error="Package installation failed.\n$o") : ($message='Missing SSL dependencies were installed successfully.');
    } else {
        $message='OpenSSL and Certbot are already installed.';
    }
} elsif ($in{'action'} eq 'reinstall_packages') {
    my @installed=grep {dependency_installed($_,$pm)} qw(openssl certbot);
    if (@installed) {
        my ($e,$o)=reinstall_packages($pm,@installed);
        $e ? ($error="Package reinstallation failed.\n$o") : ($message='Installed SSL dependencies were reinstalled successfully.');
    } else {
        $error='No SSL dependencies are currently installed.';
    }
} elsif ($in{'action'} eq 'uninstall_packages') {
    my @installed=grep {dependency_installed($_,$pm)} qw(openssl certbot);
    if (@installed) {
        my ($e,$o)=remove_packages($pm,@installed);
        $e ? ($error="Package removal failed.\n$o") : ($message='OpenSSL and Certbot were uninstalled successfully.');
    } else {
        $message='OpenSSL and Certbot are already uninstalled.';
    }
}

my @pkg_rows;
for my $pkg ('openssl','certbot') {
    push @pkg_rows, [$pkg,dependency_installed($pkg,$pm)];
}
my $missing=grep {!$_->[1]} @pkg_rows;
my $installed_count=grep {$_->[1]} @pkg_rows;

print <<'HTML';
<style>
.ols-deps{max-width:900px;margin:0 auto}.ols-hero{padding:28px 30px;border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:14px;margin-bottom:18px}.ols-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.08em;opacity:.55;font-weight:700}.ols-hero h1{margin:6px 0;font-size:28px}.ols-muted{opacity:.62;font-size:13px}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:12px;margin-bottom:16px;overflow:hidden}.ols-card h2{font-size:16px;margin:0;padding:16px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-body{padding:18px 20px}.ols-row{display:grid;grid-template-columns:1fr auto;gap:16px;padding:14px 2px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.13))}.ols-row:last-child{border-bottom:0}.ols-name{font-weight:700}.ols-desc{font-size:12px;opacity:.6;margin-top:4px}.ols-ok{color:#35a854;font-weight:700}.ols-missing{color:#d9534f;font-weight:700}.ols-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}.ols-btn{display:inline-block;padding:10px 15px;border-radius:8px;text-decoration:none;border:1px solid var(--border-color,rgba(128,128,128,.25));font-weight:700;font-size:12px;color:inherit;background:transparent;cursor:pointer}.ols-btn.primary{background:#3584e4;color:#fff;border-color:#3584e4}.ols-btn.danger{border-color:rgba(220,53,69,.35);color:#d9534f}.ols-btn:hover{background:rgba(128,128,128,.08)}.ols-btn.primary:hover{background:#2f75c7;border-color:#2f75c7}.ols-btn.danger:hover{background:rgba(220,53,69,.08)}.ols-message{padding:13px 15px;border-radius:9px;margin-bottom:16px;white-space:pre-wrap}.ols-success{background:rgba(40,167,69,.1);border:1px solid rgba(40,167,69,.25)}.ols-error{background:rgba(220,53,69,.1);border:1px solid rgba(220,53,69,.25)}.ols-warning{font-size:12px;opacity:.65;margin-top:14px}.ols-system .ols-row{padding:12px 2px}@media(max-width:650px){.ols-row{grid-template-columns:1fr}.ols-actions{flex-direction:column}.ols-btn{text-align:center}}
</style>
HTML

print "<div class='ols-deps'>";
print "<div class='ols-hero'><span class='ols-kicker'>SSL System Requirements</span><h1>Dependencies</h1><p class='ols-muted'>OpenSSL powers certificate inspection and self-signed certificates. Certbot is used to obtain and renew Let's Encrypt certificates.</p></div>";
print "<div class='ols-message ols-success'>".esc($message)."</div>" if $message;
print "<div class='ols-message ols-error'>".esc($error)."</div>" if $error;

print "<section class='ols-card'><h2>SSL Dependencies</h2><div class='ols-body'>";
for my $r (@pkg_rows) {
    my $desc=$r->[0] eq 'certbot' ? "Let's Encrypt client for certificate issuance and renewal." : 'Certificate inspection and self-signed certificate generation.';
    print "<div class='ols-row'><div><div class='ols-name'>".esc($r->[0])."</div><div class='ols-desc'>".esc($desc)."</div></div><div class='".($r->[1]?'ols-ok':'ols-missing')."'>".($r->[1]?'Installed':'Missing')."</div></div>";
}
print "<div class='ols-actions'>";
if ($missing) {
    print "<a class='ols-btn primary' href='ssl-dependencies.cgi?action=install_packages$vh_query'>Install missing</a>";
}
if ($installed_count) {
    print "<a class='ols-btn' href='ssl-dependencies.cgi?action=reinstall_packages$vh_query'>Reinstall installed</a>";
    print "<a class='ols-btn danger' href='ssl-dependencies.cgi?action=uninstall_packages$vh_query' onclick=\"return confirm('Uninstall OpenSSL and Certbot from this system? Certificate operations will stop working until they are installed again.');\">Uninstall installed</a>";
}
print "<a class='ols-btn' href='ssl-dependencies.cgi".($vh?'?vh='.&urlize($vh):'')."'>Refresh status</a>";
print "</div>";
if ($installed_count) {
    print "<p class='ols-warning'>Reinstall refreshes the currently installed dependency packages. Uninstall removes the SSL dependencies shown above; install them again before using certificate operations.</p>";
}
print "</div></section>";

print "<section class='ols-card ols-system'><h2>Detected system</h2><div class='ols-body'><div class='ols-row'><div class='ols-name'>Distribution</div><div>".esc($d{'PRETTY_NAME'} || $d{'NAME'} || 'Unknown')."</div></div><div class='ols-row'><div class='ols-name'>Package manager</div><div>".esc($pm || 'Not detected')."</div></div></div></section>";
print "<p><a href='".&html_escape($back)."'>← Back to SSL</a></p></div>";
&ui_print_footer('');
