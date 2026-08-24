#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ReadParse();

my $action = $in{'action'} || '';

if ($action !~ /^(start|stop|restart)$/) {
    &ui_print_header(undef, 'OpenLiteSpeed Service', '');
    print <<'HTML';
<style>.ols-service{max-width:760px;margin:30px auto}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:12px;padding:28px;background:var(--body-bg,transparent)}.ols-title{font-size:26px;font-weight:700;margin:0 0 7px}.ols-muted{opacity:.68;font-size:13px}.ols-actions{margin-top:22px}.ols-btn{display:inline-block;padding:8px 13px;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:7px;text-decoration:none;font-weight:600;font-size:12px}</style>
<div class="ols-service"><div class="ols-card"><div class="ols-title">OpenLiteSpeed Service</div><div class="ols-muted">Service action requested was not recognized.</div><div class="ols-actions"><a class="ols-btn" href="index.cgi">Back to dashboard</a></div></div></div>
HTML
    &ui_print_footer('');
    exit;
}

my $labels = { start => 'Start', stop => 'Stop', restart => 'Restart' };
my $label = $labels->{$action};
my $cmd = "/usr/bin/systemctl $action " . quotemeta($config{'service'}) . " 2>&1";
my $output = &backquote_command($cmd);
my $exit = $? >> 8;
my $status = &service_status();
my $running = &ols_running();
my $ok = ($exit == 0);

&ui_print_header(undef, "OpenLiteSpeed $label", '');

print <<'HTML';
<style>
.ols-service{max-width:820px;margin:24px auto}.ols-card{border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:12px;overflow:hidden;background:var(--body-bg,transparent)}.ols-head{padding:24px 26px;border-bottom:1px solid var(--border-color,rgba(128,128,128,.18));display:flex;justify-content:space-between;align-items:flex-start;gap:20px}.ols-title{font-size:25px;font-weight:700;margin:0 0 5px}.ols-muted{font-size:13px;opacity:.68}.ols-badge{padding:5px 10px;border-radius:999px;font-size:10px;font-weight:700;white-space:nowrap}.ols-ok{background:rgba(40,167,69,.14);color:#43b56b}.ols-fail{background:rgba(220,53,69,.12);color:#d9534f}.ols-body{padding:24px 26px}.ols-result{padding:16px;border-radius:9px;border:1px solid var(--border-color,rgba(128,128,128,.18));margin-bottom:20px}.ols-result strong{display:block;font-size:15px;margin-bottom:5px}.ols-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.ols-detail{padding:13px;border:1px solid var(--border-color,rgba(128,128,128,.18));border-radius:8px}.ols-label{font-size:10px;text-transform:uppercase;letter-spacing:.05em;opacity:.55;margin-bottom:4px}.ols-value{font-size:13px;font-weight:600}.ols-output{margin-top:16px}.ols-output pre{padding:14px;border-radius:8px;overflow:auto;font-size:11px;background:rgba(128,128,128,.08)}.ols-actions{margin-top:22px;display:flex;gap:8px;flex-wrap:wrap}.ols-btn{display:inline-block;padding:8px 13px;border:1px solid var(--border-color,rgba(128,128,128,.25));border-radius:7px;text-decoration:none;font-weight:600;font-size:12px}.ols-btn-primary{background:rgba(128,128,128,.1)}@media(max-width:650px){.ols-head{flex-direction:column}.ols-grid{grid-template-columns:1fr}}
</style>
HTML

print "<div class='ols-service'><div class='ols-card'>";
print "<div class='ols-head'><div><div class='ols-title'>OpenLiteSpeed Service</div><div class='ols-muted'>Service control panel</div></div>";
print $ok ? "<span class='ols-badge ols-ok'>ACTION COMPLETED</span>" : "<span class='ols-badge ols-fail'>ACTION FAILED</span>";
print "</div><div class='ols-body'>";
print "<div class='ols-result'><strong>" . ($ok ? "Service successfully $label" : "Unable to $label OpenLiteSpeed") . "</strong><span class='ols-muted'>" . ($ok ? "The requested service operation completed successfully." : "OpenLiteSpeed returned an error while processing the requested operation.") . "</span></div>";
print "<div class='ols-grid'><div class='ols-detail'><div class='ols-label'>Requested action</div><div class='ols-value'>" . &html_escape($label) . "</div></div><div class='ols-detail'><div class='ols-label'>Current status</div><div class='ols-value'>" . &html_escape($status) . "</div></div></div>";
if (!$ok && $output) { print "<div class='ols-output'><div class='ols-label'>Command output</div><pre>" . &html_escape($output) . "</pre></div>"; }
print "<div class='ols-actions'><a class='ols-btn ols-btn-primary' href='index.cgi'>Back to dashboard</a>";
print "<a class='ols-btn' href='service.cgi?action=restart'>Restart</a>" if $action ne 'restart';
print "<a class='ols-btn' href='listeners.cgi'>Listeners</a></div>";
print "</div></div></div>";

# Intentionally omit the Webmin footer navigation link.
