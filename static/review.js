
$(document).ready(function() {
    $("button#opensubmit").click(function() {
        $("#submission_dialog").removeClass("reallyhideme");
    });
    $("button#openrevert").click(function() {
        $("#revert_changes_dialog").removeClass("reallyhideme");
    });
    $("button.cancel").click(function() {
        $(".dialog").addClass("reallyhideme");
    });
    $("textarea[name='comment']").keyup(function() {
        if ($(this).val() !== "") {
            $("#submitproposal").prop("disabled", false);            
        } else {
            $("#submitproposal").prop("disabled", true);
        }
    });
    $(".dialog button[type='submit']").click(function() {
        $("input[type='checkbox']").appendTo($(this).parent());
    });
	
	$("input[type='checkbox'].subject").click(function () { 
		$(this).parents("table").find("input[type='checkbox'].predicate").prop('checked', $(this).prop('checked'));
	});
	$("span#selectall").click(function() { 
		$("input[type='checkbox']").prop('checked', !$("input[type='checkbox']").first().prop('checked'));
	});
});
