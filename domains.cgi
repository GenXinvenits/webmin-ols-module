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

sub read_config { return '' unless -f $conf; return &read_file_contents($conf); }

sub write_and_apply {
    my ($old, $new) = @_;
    my $timestamp = time();
    my $backup = "$conf.webmin-$timestamp.bak";
    my $tmp = "$conf.webmin-$timestamp.tmp";
    open(my $bfh, '>', $backup) or return (0, "Unable to create configuration backup: $!");
    print $bfh $old; close($bfh);
    open(my $tfh, '>', $tmp) or return (0, "Unable to create temporary configuration: $!");
    print $tfh $new; close($tfh);
    my $test = &backquote_command('/usr/local/lsws/bin/lshttpd -t 2>&1');
    my $test_exit = $? >> 8;
    if ($test_exit != 0) { unlink($tmp); return (0, "OpenLiteSpeed configuration validation failed.\n$test"); }
    if (!rename($tmp, $conf)) { unlink($tmp); return (0, "Unable to install the validated configuration: $!"); }
    my $restart = &backquote_command('/usr/local/lsws/bin/lswsctrl restart 2>&1');
    my $restart_exit = $? >> 8;
    if ($restart_exit != 0) {
        rename($backup, $conf);
        &backquote_command('/usr/local/lsws/bin/lswsctrl restart 2>&1');
        return (0, "OpenLiteSpeed failed to restart. The previous configuration was restored.\n$restart");
    }
    my @backups = sort { $b cmp $a } glob("$conf.webmin-*.bak");
    unlink @backups[2 .. $#backups] if @backups > 2;
    return (1, '');
}

sub vhost_names { my ($text)=@_; my @names; while ($text =~ /^\s*virtualhost\s+(\S+)\s*\{/mg) { push @names,$1; } return @names; }
sub valid_domain { my ($d)=@_; return $d =~ /^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$/; }
sub valid_alias_prefixes {
    my ($s)=@_; return 1 unless defined $s && length $s;
    for my $prefix (split(/[,\s]+/, $s)) { next unless length $prefix; return 0 unless $prefix =~ /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/; }
    return 1;
}
sub build_aliases {
    my ($domain,$prefixes)=@_; my @aliases; my %seen;
    for my $prefix (split(/[,\s]+/, $prefixes || '')) { next unless $prefix; my $alias=lc($prefix).'.'.lc($domain); next if $seen{$alias}++; push @aliases,$alias; }
    if ($domain =~ /^[^.]+\.[^.]+$/) { my $www='www.'.lc($domain); unshift @aliases,$www unless $seen{$www}++; }
    return join(' ',@aliases);
}
sub build_template_aliases {
    my ($domain,$prefixes)=@_; my @aliases; my %seen;
    if ($domain =~ /^[^.]+\.[^.]+$/) { push @aliases,'www.\$VH_NAME'; $seen{'www'}=1; }
    for my $prefix (split(/[,\s]+/, $prefixes || '')) { next unless $prefix; $prefix=lc($prefix); next if $seen{$prefix}++; push @aliases,"$prefix.\$VH_NAME"; }
    return join(' ',@aliases);
}
sub add_listener_maps {
    my ($text,$vh,$aliases)=@_;
    my @maps;
    my %seen;
    for my $alias (split(/\s+/,$aliases || '')) {
        next unless $alias;
        next if lc($alias) eq lc($vh);
        next if $seen{lc($alias)}++;
        push @maps,"    map $vh $alias\n";
    }
    my $maps=join('',@maps);
    $text =~ s{(^\s*listener\s+\S+\s*\{.*?)(^\})}{"$1$maps$2"}gems;
    return $text;
}
sub remove_listener_maps { my ($text,$vh)=@_; $text =~ s/^\s*map\s+\Q$vh\E\s+.*?\n//mg; return $text; }
sub remove_vhost_block {
    my ($text,$vh)=@_; my @lines=split(/(?<=\n)/,$text,-1); my @out; my $skip=0; my $depth=0; my $found=0;
    for my $line (@lines) {
        if (!$skip && $line =~ /^\s*virtualhost\s+\Q$vh\E\s*\{/i) { $skip=1; $found=1; $depth=0; }
        if ($skip) { my $opens=()=$line =~ /\{/g; my $closes=()=$line =~ /\}/g; $depth += $opens-$closes; $skip=0 if $depth<=0; next; }
        push @out,$line;
    }
    return (join('',@out),$found);
}
sub find_lsphp {
    my @paths; if (opendir(my $dh,$config{'lsws'})) { while(my $entry=readdir($dh)) { push @paths,"$config{'lsws'}/$entry/bin/lsphp" if $entry =~ /^lsphp[0-9.]+$/; } closedir($dh); }
    for my $p (sort {$b cmp $a} @paths) { return $p if -x $p; } return '';
}
sub load_vh_template {
    my $template=dirname(__FILE__).'/templates/vhost.conf.template'; return (0,"The OpenLiteSpeed vhost template is missing: $template") unless -f $template;
    my $content=&read_file_contents($template); return (0,"Unable to read the OpenLiteSpeed vhost template: $template") unless defined $content; return (1,$content);
}
sub build_vhconf {
    my ($domain,$aliases,$alias_prefixes)=@_; my ($template_ok,$template)=load_vh_template(); return '' unless $template_ok;
    my $lsphp=find_lsphp(); my $php='';
    if ($lsphp) { $php=qq{

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
}; }
    my $alias_line="vhAliases                        ".build_template_aliases($domain,$alias_prefixes)."\n";
    $template =~ s/__DOMAIN__/$domain/g; $template =~ s/__VH_ALIASES_LINE__/$alias_line/; $template =~ s/__PHP_CONFIG__/$php/; return $template;
}

my $content=read_config();
if ($in{'action'} eq 'add') {
    my $domain=lc($in{'domain'} || ''); $domain =~ s/^\s+|\s+$//g;
    my $alias_prefixes=lc($in{'alias_prefixes'} || ''); $alias_prefixes =~ s/^\s+|\s+$//g; my $aliases='';
    if (!valid_domain($domain)) { $error='Enter a valid domain name, for example example.com.'; }
    elsif (!valid_alias_prefixes($alias_prefixes)) { $error='Aliases must contain subdomain prefixes only, separated by commas, for example xyz,account,community. Do not enter the domain name.'; }
    elsif (grep {lc($_) eq $domain} vhost_names($content)) { $error="The domain $domain is already registered."; }
    else {
        $aliases=build_aliases($domain,$alias_prefixes); my $vh_root="$domain_base/$domain"; my $vh_conf="$vh_root/conf/vhconf.conf"; my $public_html="$vh_root/public_html";
        my $paths_ok=eval {
            make_path("$vh_root/conf",$public_html,"$vh_root/logs","$vh_root/cgi-bin","$public_html/.well-known/acme-challenge","$vh_root/cachedata");
            system('/bin/chown','root:nogroup',$vh_root)==0 or die "Unable to set domain root ownership: $!"; system('/bin/chmod','755',$vh_root)==0 or die "Unable to set domain root permissions: $!";
            for my $path ($public_html,"$vh_root/cgi-bin","$vh_root/cachedata") { system('/bin/chown','-R','www-data:www-data',$path)==0 or die "Unable to set ownership for $path: $!"; system('/bin/chmod','-R','755',$path)==0 or die "Unable to set permissions for $path: $!"; }
            system('/bin/chown','-R','lsadm:nogroup',"$vh_root/conf")==0 or die "Unable to set configuration ownership: $!"; system('/bin/chmod','-R','755',"$vh_root/conf")==0 or die "Unable to set configuration permissions: $!";
            system('/bin/chown','-R','root:nogroup',"$vh_root/logs")==0 or die "Unable to set log ownership: $!"; system('/bin/chmod','-R','750',"$vh_root/logs")==0 or die "Unable to set log permissions: $!";
            1;
        };
        if (!$paths_ok) { $error="Unable to create the domain directories: $@"; }
        elsif (-e $vh_conf) { $error="The virtual host configuration already exists: $vh_conf"; }
        else {
            my $vh_config=build_vhconf($domain,$aliases,$alias_prefixes); if (!$vh_config) { $error='Unable to build the virtual host configuration from the module template.'; }
            else { my $fh; if (!open($fh,'>',$vh_conf)) { $error="Unable to create $vh_conf: $!"; } else { print $fh $vh_config; close($fh); } }
            if (!$error) {
                my $block="\nvirtualhost $domain {\n    vhRoot $vh_root/\n    configFile $vh_conf\n    allowSymbolLink 1\n    enableScript 1\n    restrained 1\n}\n";
                my $new=add_listener_maps($content.$block,$domain,$aliases); my ($ok,$out)=write_and_apply($content,$new);
                if ($ok) { $message="Domain $domain was added successfully."; } else { unlink($vh_conf); $error=$out; }
            }
        }
    }
}
elsif ($in{'action'} eq 'remove') {
    my $domain=$in{'domain'} || ''; $domain =~ s/[^A-Za-z0-9._-]//g;
    if (!$domain || !grep {$_ eq $domain} vhost_names($content)) { $error='The selected domain is not registered.'; }
    elsif ($in{'confirm_remove'} ne 'yes') { $error="Deletion of $domain is permanent and cannot be undone. Please confirm the deletion twice."; }
    else {
        my ($new,$found)=remove_vhost_block($content,$domain); $new=remove_listener_maps($new,$domain);
        if ($found) {
            my ($ok,$out)=write_and_apply($content,$new);
            if ($ok) {
                my $vh_conf="$domain_base/$domain/conf/vhconf.conf"; unlink($vh_conf) if -f $vh_conf; my $vh_root="$domain_base/$domain"; my @cleanup_errors;
                if (-d $vh_root) { eval { my $errors; remove_tree($vh_root,{error=>\$errors}); push @cleanup_errors,"Unable to remove domain directory $vh_root" if $errors && @$errors; }; push @cleanup_errors,"Unable to remove domain directory $vh_root: $@" if $@; }
                my $cert_archive="/etc/letsencrypt/archive/$domain"; my $cert_live="/etc/letsencrypt/live/$domain";
                for my $cert_dir ($cert_archive,$cert_live) { if (-d $cert_dir) { eval { my $errors; remove_tree($cert_dir,{error=>\$errors}); push @cleanup_errors,"Unable to remove SSL certificate directory $cert_dir" if $errors && @$errors; }; push @cleanup_errors,"Unable to remove SSL certificate directory $cert_dir: $@" if $@; } }
                if (@cleanup_errors) { $message="Domain $domain was removed from OpenLiteSpeed, but cleanup was incomplete."; $error=join("\n",@cleanup_errors); } else { $message="Domain $domain was removed successfully. Its OpenLiteSpeed configuration, domain directory and SSL certificate directories were deleted."; }
            } else { $error=$out; }
        } else { $error='Unable to locate the virtual host configuration block.'; }
    }
}

$content=read_config(); my @domains=vhost_names($content);
print <<'HTML';
<style>
.ols-domains{max-width:1050px;margin:0 auto}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:12px;margin-bottom:16px;overflow:hidden}.ols-card h2{font-size:16px;margin:0;padding:16px 20px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-body{padding:18px 20px}.ols-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.ols-field label{display:block;font-size:11px;font-weight:700;margin-bottom:6px;opacity:.7}.ols-field input{width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:4px;background:transparent;color:inherit}.ols-note,.ols-field-help{font-size:11px;line-height:1.45;opacity:.58}.ols-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:14px}.ols-btn{display:inline-block;padding:8px 13px;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;color:inherit;background:transparent;cursor:pointer}.ols-list{border:1px solid var(--border-color,rgba(128,128,128,.22));border-radius:8px;overflow:hidden}.ols-row{display:grid;grid-template-columns:minmax(220px,1fr) minmax(250px,1fr) 100px;gap:12px;align-items:center;padding:11px 13px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.16))}.ols-row:last-child{border-bottom:0}.ols-head{font-size:10px;text-transform:uppercase;letter-spacing:.05em;font-weight:700;opacity:.58}.ols-domain{font-weight:700}.ols-danger{color:#d9534f}.ols-add-highlight{border-color:rgba(53,132,228,.38);background:linear-gradient(180deg,rgba(53,132,228,.08),rgba(53,132,228,.025));box-shadow:0 2px 10px rgba(53,132,228,.06)}.ols-add-highlight h2{background:rgba(53,132,228,.07);border-bottom-color:rgba(53,132,228,.18)}.ols-add-intro{display:flex;align-items:flex-start;gap:12px;margin-bottom:18px}.ols-add-icon{width:34px;height:34px;flex:0 0 34px;border-radius:9px;display:flex;align-items:center;justify-content:center;background:rgba(53,132,228,.13);color:#3584e4;font-size:20px}.ols-add-copy strong{display:block;font-size:13px;margin-bottom:3px}.ols-add-copy span{display:block;font-size:12px;line-height:1.5;opacity:.68}.ols-alias-input{display:flex;align-items:center;border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:4px;overflow:hidden}.ols-alias-input input{border:0!important;border-radius:0!important;min-width:0}.ols-alias-suffix{padding:0 10px;font-size:12px;opacity:.62;white-space:nowrap}.ols-notification,.ols-error-notification{display:flex;align-items:flex-start;gap:10px;padding:12px 15px;margin:0 0 16px;border-radius:8px;font-size:13px;font-weight:600}.ols-notification{border:1px solid rgba(40,167,69,.28);background:rgba(40,167,69,.10)}.ols-notification:before{content:'✓';display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:rgba(40,167,69,.18);color:#35a854}.ols-error-notification{border:1px solid rgba(220,53,69,.28);background:rgba(220,53,69,.10)}.ols-error-notification:before{content:'!';display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:rgba(220,53,69,.18);color:#d9534f}.ols-ssl-options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}.ols-ssl-option{border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:8px;padding:11px 12px}.ols-ssl-option label{display:block;font-size:12px;font-weight:700;cursor:pointer}.ols-ssl-option input{width:auto;margin-right:7px}.ols-ssl-option span{display:block;margin:5px 0 0 22px;font-size:11px;line-height:1.4;opacity:.6}.ols-ssl-email{margin-top:10px;display:none}.ols-ssl-email.visible{display:block}
</style>
HTML

print "<div class='ols-domains'>";
print "<div class='ols-notification'>".&html_escape($message)."</div>" if $message;
print "<div class='ols-error-notification'>".&html_escape($error)."</div>" if $error;
print "<section class='ols-card ols-add-highlight'><h2>Add Domain</h2><div class='ols-body'><div class='ols-add-intro'><div class='ols-add-icon'>+</div><div class='ols-add-copy'><strong>Register a new website with OpenLiteSpeed</strong><span>Creates the virtual host, public_html, logs, CGI directory, cache directory and listener mappings automatically.</span></div></div><form method='post' action='domains.cgi'><input type='hidden' name='action' value='add'><div class='ols-grid'><div class='ols-field'><label for='ols-domain'>Domain</label><input id='ols-domain' name='domain' type='text' placeholder='example.com' required><span class='ols-field-help'>Enter the primary domain, without http:// or https://.</span></div><div class='ols-field'><label for='ols-alias-prefixes'>Aliases / Subdomains</label><div class='ols-alias-input'><input id='ols-alias-prefixes' name='alias_prefixes' type='text' placeholder='xyz,account,community' autocomplete='off'><span class='ols-alias-suffix' id='ols-alias-suffix'>.example.com</span></div><span class='ols-field-help'>Enter prefixes separated by commas, e.g. xyz,account,community.</span></div></div><div class='ols-actions'><button class='ols-btn' type='submit'>Add Domain</button><a class='ols-btn' href='index.cgi'>Back to Websites</a></div></form></div></section>";
print "<section class='ols-card'><h2>Registered Domains</h2><div class='ols-body'><p class='ols-note'>Removing a domain unregisters its OpenLiteSpeed configuration and listener mappings, and deletes its domain directory and SSL certificate directories.</p><div class='ols-list'><div class='ols-row ols-head'><div>Domain</div><div>Virtual Host</div><div>Action</div></div>";
if (!@domains) { print "<div class='ols-body ols-note'>No domains registered.</div>"; }
else { for my $d (@domains) { print "<div class='ols-row'><div class='ols-domain'>".&html_escape($d)."</div><div>".&html_escape("$domain_base/$d")."</div><div><form method='post' action='domains.cgi' onsubmit=\"return confirm('WARNING: Delete $d permanently? This removes the domain files, configuration and SSL certificates and cannot be undone.');\"><input type='hidden' name='action' value='remove'><input type='hidden' name='domain' value='".&quote_escape($d)."'><input type='hidden' name='confirm_remove' value='yes'><button class='ols-btn ols-danger' type='submit'>Remove</button></form></div></div>"; } }
print "</div></div></section></div>";

print <<'HTML';
<script>
(function(){
 var domain=document.getElementById('ols-domain'),suffix=document.getElementById('ols-alias-suffix');
 function updateSuffix(){if(!domain||!suffix)return;var v=domain.value.trim().replace(/^https?:\/\//i,'').replace(/\/.*$/,'');suffix.textContent=v?'.'+v:'.example.com';}
 if(domain)domain.addEventListener('input',updateSuffix);updateSuffix();
})();
</script>
HTML
&ui_print_footer('index.cgi');
