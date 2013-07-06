$(document).ready(function() {
    $(".tabnav-tab").click(function() {

        $(this).parent().parent().find(".tabnav-tab").removeClass("selected");
        $(this).addClass("selected");

        $(".content-tab").addClass('reallyhideme');
	$($(this).attr('href')).removeClass('reallyhideme');
	return false;
    });
});
