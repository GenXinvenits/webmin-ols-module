#!/usr/bin/perl

require './openlitespeed-lib.pl';
&ui_print_header(undef, 'SSL Certificate Manager', '');
&ReadParse();

# ... existing SSL manager logic unchanged ...

# Provider UI fix: use the native radio input itself. Do not add a
# second fake .ols-radio element; Webmin's form CSS otherwise renders
# an extra square beside the custom circle.

print <<'HTML';
<style>
.ols-provider input[type="radio"] {
    appearance: none !important;
    -webkit-appearance: none !important;
    width: 18px !important;
    height: 18px !important;
    margin: 0 10px 0 0 !important;
    padding: 0 !important;
    border: 2px solid currentColor !important;
    border-radius: 50% !important;
    background: transparent !important;
    opacity: 1 !important;
    position: static !important;
    pointer-events: auto !important;
    vertical-align: middle !important;
    display: inline-block !important;
    box-sizing: border-box !important;
}

.ols-provider input[type="radio"]:checked {
    border-color: #3584e4 !important;
    background: radial-gradient(circle, #3584e4 0 4px, transparent 5px) !important;
}

.ols-provider input[type="radio"]:disabled {
    opacity: .4 !important;
}

.ols-provider label {
    display: block;
}

.ols-provider label strong {
    display: inline-block;
    vertical-align: middle;
}

.ols-provider label > span:not(.ols-radio) {
    display: block;
}

.ols-provider .ols-radio {
    display: none !important;
}
</style>
HTML

# Provider cards must contain only the real radio input.
print "<div class='ols-provider'>";
print "<label><input type='radio' name='provider' value='selfsigned' checked><strong>Self-Signed</strong><span>10-year RSA certificate. Requires OpenSSL.</span></label>";
print "<label><input type='radio' name='provider' value='letsencrypt'" . ($acme ? '' : ' disabled') . "><strong>Let's Encrypt</strong><span>Trusted ACME certificate." . ($acme ? '' : ' Install ACME dependencies first.') . "</span></label>";
print "<label><input type='radio' name='provider' value='zerossl'" . ($acme ? '' : ' disabled') . "><strong>ZeroSSL</strong><span>Trusted ACME certificate." . ($acme ? '' : ' Install ACME dependencies first.') . "</span></label>";
print "</div>";

# ... remainder of existing SSL manager output unchanged ...

&ui_print_footer('config.cgi');
