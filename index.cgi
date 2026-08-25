#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'OpenLiteSpeed', '');
&ReadParse();

my $conf = "$config{'lsws'}/conf/httpd_config.conf";
my @vhosts;
if (open(my $fh, '<', $conf)) { while (my $line = <$fh>) { if ($line =~ /^\s*virtualhost\s+(\S+)\s*\{/) { push(@vhosts, $1); } } close($fh); }

sub get_value { my ($content,$name)=@_; if ($content =~ /^\s*\Q$name\E\s+(.+?)\s*$/m) { my $value=$1; $value =~ s/\s+$//; return $value; } return ''; }
sub resolve_value { my ($value,$vh)=@_; return '' unless defined $value; my $vh_root="$config{'lsws'}/domains/$vh"; my $server_root=$config{'lsws'}; $value =~ s/\$VH_NAME/$vh/g; $value =~ s/\$VH_ROOT/$vh_root/g; $value =~ s/\$SERVER_ROOT/$server_root/g; return $value; }
sub ssl_ready {
    my ($vh,$content) = @_;
    return 0 unless $content =~ /^\s*vhssl\s*\{/m;
    my $root = "$config{'lsws'}/cert/$vh";
    return (-f "$root/fullchain.pem" && -f "$root/privkey.pem") ? 1 : 0;
}

my $sort=$in{'sort'}||'newest';
$sort='newest' unless $sort =~ /^(?:newest|oldest|az|za)$/;
if ($sort eq 'az' || $sort eq 'za') {
    @vhosts = sort { lc($a) cmp lc($b) || $a cmp $b } @vhosts;
    @vhosts = reverse @vhosts if $sort eq 'za';
} else {
    @vhosts = sort {
        my $am=(stat("$config{'lsws'}/domains/$a/conf/vhconf.conf"))[9] || (stat("$config{'lsws'}/domains/$a"))[9] || 0;
        my $bm=(stat("$config{'lsws'}/domains/$b/conf/vhconf.conf"))[9] || (stat("$config{'lsws'}/domains/$b"))[9] || 0;
        $sort eq 'newest' ? ($bm <=> $am || lc($a) cmp lc($b)) : ($am <=> $bm || lc($a) cmp lc($b));
    } @vhosts;
}

my $per_page=20; my $page=$in{'page'}||1; $page=~s/\D//g; $page=1 if !$page||$page<1; my $total=scalar @vhosts; my $pages=$total?int(($total+$per_page-1)/$per_page):1; $page=$pages if $page>$pages; my $start=($page-1)*$per_page; my $end=$start+$per_page-1; $end=$total-1 if $end>=$total;
my $status=&service_status(); my $version=&ols_version(); my $running=&ols_running();

my $registered_domains=$total;
my $running_domains=0;
my $stopped_domains=0;
for my $vh (@vhosts) {
    my $vhconf="$config{'lsws'}/domains/$vh/conf/vhconf.conf";
    if (-f $vhconf) { $running_domains++; }
    else { $stopped_domains++; }
}

print <<'HTML';
<style>
.ols-wrap{max-width:1200px;margin:0 auto}.ols-hero{padding:22px 24px;margin:0 0 20px;border-radius:10px;border:1px solid var(--border-color,rgba(128,128,128,.25));background:var(--body-bg,transparent)}.ols-hero-top{display:flex;align-items:flex-start;justify-content:space-between;gap:24px}.ols-hero h1{margin:0 0 5px;font-size:26px}.ols-hero p{margin:0;opacity:.72;font-size:13px}.ols-details{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:20px}.ols-detail{padding:10px 12px;border:1px solid var(--border-color,rgba(128,128,128,.18));border-radius:7px}.ols-detail-label{font-size:10px;text-transform:uppercase;letter-spacing:.05em;opacity:.58;margin-bottom:3px}.ols-detail-value{font-size:12px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ols-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:10px}.ols-stat{padding:12px 14px;border:1px solid var(--border-color,rgba(128,128,128,.18));border-radius:7px}.ols-stat-label{font-size:10px;text-transform:uppercase;letter-spacing:.05em;opacity:.58;margin-bottom:4px}.ols-stat-value{font-size:22px;font-weight:700;line-height:1.1}.ols-stat-green{color:#43b56b}.ols-stat-red{color:#d9534f}.ols-controls{display:flex;gap:7px;flex-wrap:wrap;margin-top:18px}.ols-control{display:inline-block;padding:7px 12px;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:6px;text-decoration:none;font-size:12px;font-weight:600}.ols-control.primary{background:rgba(40,167,69,.12)}.ols-control.danger{background:rgba(220,53,69,.10)}.ols-status-running{color:#43b56b}.ols-status-stopped{color:#d9534f}.ols-list{border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:10px;overflow:hidden;background:var(--body-bg,transparent)}.ols-row{display:grid;grid-template-columns:minmax(220px,1fr) minmax(420px,2.4fr) 150px 100px;align-items:center;gap:16px;padding:13px 16px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.18))}.ols-row:last-child{border-bottom:0}.ols-head{font-size:11px;text-transform:uppercase;letter-spacing:.05em;font-weight:700;opacity:.68;background:var(--table-header-bg,rgba(128,128,128,.08))}.ols-domain{font-weight:700}.ols-subdomains{margin-top:3px;font-size:11px;opacity:.65;line-height:1.4}.ols-root{font-size:12px;opacity:.72;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ols-meta{font-size:11px;opacity:.72}.ols-status{display:inline-block;width:max-content;padding:3px 8px;border-radius:999px;font-size:10px;font-weight:700;background:rgba(40,167,69,.14);color:#43b56b}.ols-status.off{background:rgba(128,128,128,.14);color:inherit;opacity:.65}.ols-manage{text-align:right}.ols-manage a{text-decoration:none;font-weight:600}.ols-add-domain{display:inline-block;padding:7px 12px;border:1px solid rgba(53,132,228,.38);border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;color:inherit;background:rgba(53,132,228,.07)}.ols-section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.ols-sort{display:flex;align-items:center;gap:8px}.ols-sort label{font-size:11px;opacity:.62}.ols-sort select{padding:7px 10px;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:6px;background:transparent;color:inherit;font-size:12px}.ols-pagination{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:16px}.ols-pages{display:flex;gap:5px;flex-wrap:wrap}.ols-page{display:inline-block;min-width:30px;padding:6px 9px;text-align:center;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:6px;text-decoration:none}.ols-page.current{font-weight:700;background:rgba(128,128,128,.12)}.ols-empty{padding:24px;opacity:.72}.ols-domain-actions{display:flex;justify-content:flex-end;margin-top:12px}@media(max-width:800px){.ols-hero-top{flex-direction:column}.ols-details{grid-template-columns:1fr 1fr}.ols-stats{grid-template-columns:1fr 1fr}.ols-row{grid-template-columns:1fr 1fr}.ols-head{display:none}.ols-manage{text-align:left}.ols-section-head{align-items:flex-start;flex-direction:column}.ols-sort{width:100%}.ols-sort select{flex:1}}@media(max-width:520px){.ols-stats{grid-template-columns:1fr}}
</style>
HTML

print "<div class='ols-wrap'>";
print "<div class='ols-hero'><div class='ols-hero-top'><div><h1>OpenLiteSpeed</h1><p>Server status, version, configuration and service controls.</p></div><div class='ols-meta'>";
print $running?"<span class='ols-status-running'><b>● Running</b></span>":"<span class='ols-status-stopped'><b>● Stopped</b></span>"; print "</div></div>";
print "<div class='ols-details'><div class='ols-detail'><div class='ols-detail-label'>Status</div><div class='ols-detail-value'>$status</div></div><div class='ols-detail'><div class='ols-detail-label'>Version</div><div class='ols-detail-value'>".&html_escape($version)."</div></div><div class='ols-detail'><div class='ols-detail-label'>Installation</div><div class='ols-detail-value'>".&html_escape($config{'lsws'})."</div></div><div class='ols-detail'><div class='ols-detail-label'>Configuration</div><div class='ols-detail-value'>".&html_escape($config{'config'})."</div></div></div>";
print "<div class='ols-stats'><div class='ols-stat'><div class='ols-stat-label'>Registered domains</div><div class='ols-stat-value'>".$registered_domains."</div></div><div class='ols-stat'><div class='ols-stat-label'>Running domains</div><div class='ols-stat-value ols-stat-green'>".$running_domains."</div></div><div class='ols-stat'><div class='ols-stat-label'>Stopped / suspended</div><div class='ols-stat-value ols-stat-red'>".$stopped_domains."</div></div></div>";
print "<div class='ols-controls'><a class='ols-control primary' href='service.cgi?action=start'>Start</a><a class='ols-control danger' href='service.cgi?action=stop'>Stop</a><a class='ols-control' href='service.cgi?action=restart'>Restart</a><a class='ols-control' href='listeners.cgi'>Listeners</a></div>";
print "<div class='ols-domain-actions'><a class='ols-add-domain' href='domains.cgi'>Add / Remove Domains</a></div></div>";
print "<div class='ols-section-head'><h2>Websites</h2><div class='ols-sort'><label for='domain-sort'>Sort by</label><select id='domain-sort' onchange=\"window.location='index.cgi?sort='+encodeURIComponent(this.value)\"><option value='newest'".($sort eq 'newest'?' selected':'').">Newest first</option><option value='oldest'".($sort eq 'oldest'?' selected':'').">Oldest first</option><option value='az'".($sort eq 'az'?' selected':'').">Alphabetical (A–Z)</option><option value='za'".($sort eq 'za'?' selected':'').">Alphabetical (Z–A)</option></select></div></div><div class='ols-list'><div class='ols-row ols-head'><div>Domain</div><div>Document Root</div><div>Status</div><div>Action</div></div>";
if(!$total){print "<div class='ols-empty'>No virtual hosts were found in <code>".&html_escape($conf)."</code>.</div>";}else{for(my $i=$start;$i<=$end;$i++){my $vh=$vhosts[$i];my $root="$config{'lsws'}/domains/$vh";my $vhconf="$root/conf/vhconf.conf";my $conf_exists=-f $vhconf;my($domain,$docroot,$aliases)=('','','');my($ssl,$rewrite)=(0,0);if($conf_exists){my $content=&read_file_contents($vhconf);$domain=resolve_value(get_value($content,'vhDomain'),$vh);$docroot=resolve_value(get_value($content,'docRoot'),$vh);$aliases=resolve_value(get_value($content,'vhAliases'),$vh);$ssl=ssl_ready($vh,$content);$rewrite=1 if $content=~/^\s*rewrite\s*\{/m;}$domain=$vh unless $domain;$docroot="$root/public_html" unless $docroot;my @subdomains=$aliases?split(/\s+/,$aliases):();@subdomains=grep{$_ ne $domain}@subdomains;print "<div class='ols-row'><div><div class='ols-domain'>".&html_escape($domain)."</div>";print "<div class='ols-subdomains'>".&html_escape(join(', ',@subdomains))."</div>" if @subdomains;print "</div><div class='ols-root'>".&html_escape($docroot)."</div><div>";print $conf_exists?"<span class='ols-status'>READY</span>":"<span class='ols-status off'>NOT CONFIGURED</span>";print "<div class='ols-meta'>";print "SSL ".($ssl?'enabled':'not configured')." · Rewrite ".($rewrite?'on':'off') if $conf_exists;print "</div></div><div class='ols-manage'>";print $conf_exists?"<a href='config.cgi?vh=".&urlize($vh)."'>Manage →</a>":"<span class='ols-meta'>Unavailable</span>";print "</div></div>";}}
print "</div>";
if($total>$per_page){my $base='index.cgi?sort='.urlize($sort).'&page=';print "<div class='ols-pagination'><div class='ols-meta'>Showing ".($start+1)."–".($end+1)." of $total domains</div><div class='ols-pages'>";print "<a class='ols-page' href='".$base.($page-1)."'>‹</a>" if $page>1;for(my $p=1;$p<=$pages;$p++){next if $pages>8&&$p!=1&&$p!=$pages&&abs($p-$page)>1;print "<a class='ols-page".($p==$page?' current':'')."' href='".$base.$p."'>$p</a>";}print "<a class='ols-page' href='".$base.($page+1)."'>›</a>" if $page<$pages;print "</div></div>";}
print "</div>";
&ui_print_footer('');
