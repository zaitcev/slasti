// <!-- CDATA? Laffo. -->
// <!-- <script type="text/javascript"> -->

function preload_title(fetch_url, title_id, button_id) {

    // Fetch the user input from the form
    var tgt_url = document.editform.href.value;
    var url = fetch_url + "?url=" + encodeURIComponent(tgt_url);

    // Get the reference to the result
    var t = document.getElementById(title_id);
    var b = document.getElementById(button_id);

    // Legacy DOM:
    // document.editform.title1
    // document.forms.editform.title1
    // document.forms["editform"].title1

    // XXX verify that url at least starts with an HTTP scheme and "://"

    // Screw IE6, just use the decent way.
    var req = new XMLHttpRequest();
    var title_str = null;
    var timer = null;

    function state_handler() {
        if (req.readyState == 4) {
            if (req.status == 200) {
               // No need to check req.getResponseHeader("Content-Type") for us.
               t.value = req.responseText;
            }
            // Not saving req.statusText for UI predictability.
            if (timer)
               clearTimeout(timer);
            b.disabled = false;
        }
    }

    function req_timeout() {
        req.abort();
        alert("abort");
        b.disabled = false;
    }

    // Actually Window.setTimeout()
    // 5s more than server-side. Just so.
    timer = setTimeout(req_timeout, 30*1000);
    b.disabled = true;

    req.onreadystatechange = state_handler;
    req.open("GET", url);
    req.send(null);

    // alert(title_ref.value);
    return false;
}
