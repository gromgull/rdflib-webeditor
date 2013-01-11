
$(document).ready(function() {
    $("button#openreject").click(function() {
        $("#reject_dialog").removeClass("reallyhideme");
    });
    $("button#openaccept").click(function() {
        $("#accept_dialog").removeClass("reallyhideme");
    });
    $("button.cancel").click(function() {
        $(this).parent().parent().addClass("reallyhideme");
    });
    $("textarea[name='comment']").keyup(function() {
        if ($(this).val() !== "") {
            $("button#reject").prop("disabled", false);            
        } else {
            $("button#reject").prop("disabled", true);
        }
    });
});
