(function ($) {
    $.fn.renderAppend = function(templateId, input, callback) {
        //return this.each(function() {
            var obj = $("<span></span>");
            $(this).append(obj);
            return obj.render(templateId, input, callback);
    //});
    }

    $.fn.renderAfter = function(templateId, input, callback) {
        var obj = $("<span></span>");
        $(obj).insertAfter($(this));
        return obj.render(templateId, input, callback);
    }

    $.fn.render = function(templateId, input, callback) {
        var template = $("#templates #" + templateId);
        if (template) {
            template = template.clone();
            var content = template.html();
            var matches = content.match(/%\((\w+)\)/g);
            if (matches) {
                for (var i = 0; i < matches.length; i++) {
                    val = input[matches[i].substring(2, matches[i].length-1)] || "";
                    val = val.replace(/"/g, '&quot;');
                    content = content.replace(matches[i], val);
                }
            } else {
                console.log("WARNING: no matches found: " + content);
            }

            var cont = $(content).clone()
            var conditional = function(n, e) {
                var p = $(this).parent();
                var val = $(this).attr("if").split(/\s+/);
                var rval = true;
                var test = 'and';
                for (var i = 0; i < val.length; i++) {
                    if (i % 2 == 1) {
                        test = val[i];
                        if (test !== 'and' && test !== 'or') {
                            console.log("expected 'and' or 'or' in expression");
                            return;
                        }
                    } else {
                        var v = input[val[i]];
                        v = !(v == undefined || v == null || v == false || v === "");
                        if (test === 'and') {
                            rval = rval && v;
                        } else {
                            rval = rval || v;
                        }
                    }
                }
                if (rval) {
                    $(this).next("[else]").detach();
                    $(this).replaceWith($(this).contents());
                } else {
                    $(this).next("[else]").replaceWith($(this).next("[else]").contents());
                    $(this).detach();
                }
                // replaceWith actions disconnect nested ifs
                //$(p).find("[if]").each(conditional);
            };
            $(cont).find("[if]").each(
                conditional
            );
            $(this).replaceWith(cont);
            if (callback) {
                callback(cont);
            }
            return cont;
        }
        console.log("ERROR: couldn't find template: " + templateId);
        // TODO: or error?
        return this;
    }
}(jQuery));
