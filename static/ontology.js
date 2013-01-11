
function initOntologyPage() {
    // TODO: if this is all set up right, then it could be moved to base.html (or create a base.js for it)
    $(".pagenav-tab").click(function() {
        if (!$(this).is(".selected")) {
            $(this).parent().parent().find("a.selected").removeClass("selected");
            $(this).addClass("selected");
            $(".content-tab").css("display", "none");
            $($(this).attr("data-id")).css("display", "block");
        }
    });
}
