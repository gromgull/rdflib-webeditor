$(document).ready(function() {
    //$(".accepted").addClass("reallyhideme");
    //$(".rejected").addClass("reallyhideme");
    $("#showall").click(function() {
        $(".proposal").removeClass("reallyhideme");
    });
    $("#showproposed").click(function() {
        $(".proposal.proposed").removeClass("reallyhideme");
        $(".proposal.accepted").addClass("reallyhideme");
        $(".proposal.rejected").addClass("reallyhideme");
    });
    $("#showaccepted").click(function() {
        $(".proposal.accepted").removeClass("reallyhideme");
        $(".proposal.proposed").addClass("reallyhideme");
        $(".proposal.rejected").addClass("reallyhideme");
    });
    $("#showrejected").click(function() {
        $(".proposal.rejected").removeClass("reallyhideme");
        $(".proposal.proposed").addClass("reallyhideme");
        $(".proposal.accepted").addClass("reallyhideme");
    });
    $("#showproposed .counter").html($(".proposal.proposed").length);
    $("#showaccepted .counter").html($(".proposal.accepted").length);
    $("#showrejected .counter").html($(".proposal.rejected").length);
});
