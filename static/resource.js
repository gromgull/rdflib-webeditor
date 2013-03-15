var uri_re = /^<[^>]+>$/;
var literal_re = /^"[^"]*"(?:\^\^[^\s]+|@[^\s]+|)$/;
var num_re = /^[+-]?[0-9]+(?:(?:\.?[0-9]+(?:(?:(?:E|e)?[+-]?[0-9]+)|)|))$/;
var val_re = /^"[^"]*"(?:\^\^[^\s]+|@[^\s]+|)|<[^>]+>|[+-]?[0-9]+(?:(?:\.?[0-9]+(?:(?:(?:E|e)?[+-]?[0-9]+)|)|))$/;
var quad_re = /^<([^>]+)>\s+<([^>]+)>\s+("[^"]*"(?:\^\^[^\s]+|@[^\s]+|)|<[^>]+>|[+-]?[0-9]+(?:(?:\.?[0-9]+(?:(?:(?:E|e)?[+-]?[0-9]+)|)|)))(?:\s+<([^>]+)>|)$/;

// change this to false to turn off autoblur
var auto_blur = true;

var initialise = function(ontology, predicateData) {

    var gen_quad = function(subject, predicate, value, context) {
        var src = "";
        var val = value.trim();
        if (val !== "") { // ignore empty values
            src += "<" + subject + "> <" + predicate + "> ";
            if (val.match(num_re) || val.match(literal_re) || val.match(uri_re)) {
                src += val;
            } else { // just assuming anything else is a URI 
                // (TODO: not-assuming requires some modification to the way the select2 boxes work)
                src += "<" + val + ">";
            }
            if (context) {
                src += " <" + context + ">";
            }
        }
        return src;
    };

    // generates nquads source code from the properties table
    generate_nquads_source = function() {
        var src = "";
        var subj = $("table.properties").attr("data-subject");
        var ctx = $("table.properties").attr("data-context");
        $("table.properties tbody > tr").each(function() {
            var pred = $(this).find("td.property div.uri").html();
            // TODO: should we do a sanity check on pred?
            if (pred && !$(this).is(".removed")) {
                var val = $(this).find("td.value div.uri a").html() || 
                    $(this).find("td.value div.uri").html();
                src += gen_quad(subj, pred, val, ctx) + "\n";
            }
        });
        // remove trailing \n
        src = src.substring(0, src.length-1);
        return src;
    }

    generate_diff = function() {
        var subj = $("table.properties").attr("data-subject");
        var ctx = $("table.properties").attr("data-context");
        var deleted = [];
        var added = [];
        $("table.properties tbody > tr").each(function() {
            // check to make sure editing isn't active, which it should never be able to be if getting here!
            if ($(this).find("td.value").is(".editing")) {
                // TODO: error
                return false;
            }
            var pred = $(this).find("td.property div.uri").html();
            // sanity check on pred
            if (pred === "" || pred === "\"\"") {
                // added predicates can == """" if nothing is entered.
                return;
            }
            var val = $(this).find("td.value div.uri a").html() || 
                $(this).find("td.value div.uri").html();
            if ($(this).is(".deleted")) {
                deleted.push(gen_quad(subj, pred, val, ctx).match(quad_re).splice(1));
            } else if ($(this).is(".added")) {
                added.push(gen_quad(subj, pred, val, ctx).match(quad_re).splice(1));
            } else if ($(this).is(".modified")) {
                added.push(gen_quad(subj, pred, val, ctx).match(quad_re).splice(1));
                deleted.push(gen_quad(subj, pred, 
                                      $(this).find("td.value").attr("orig-uri"), ctx)
                             .match(quad_re).splice(1));
            }
        });
        return {'deleted': deleted, 'added': added}
    }

    var wrapURI = function(div) {
        var val = $(div).html();
        if (val.indexOf(ontology.context) == 0) {
            $(div).html(
                // TODO: make sure this opens in a new tab/window !!!!!!!!
                // or at least gives a message if the current changes haven't been saved
                $("<a href=\"\?resource_=" + encodeURIComponent(val) + "\"/>").html(val)
            );
        }
    };

    var newRow = function(predicate, value) {
        var row = get_template('row');

        if (predicate != undefined) {
            $(row).find(".property .label").html(predicate.label);
            $(row).find(".property .qname").html(predicate.qname);
            $(row).find(".property .uri").html(predicate.uri);
        } else {
            // enable predicate editing mode
            $(row).find(".property").removeClass("base").addClass("editing").addClass("new");
        }

        if (value != undefined) {
            $(row).find(".value .label").html(value.label);
            $(row).find(".value .qname").html(value.qname);
            $(row).find(".value .uri").html(value.uri);

            var val = value.uri;
            if (value.type === "URI") {
                val = '<' + val + '>';
                wrapURI($(row).find(".value div.uri"));
            }
            $(row).find(".value textarea").val(val);
            $(row).find("td.value").attr("orig-label", value.label);
            $(row).find("td.value").attr("orig-qname", value.qname);
            $(row).find("td.value").attr("orig-uri", value.uri);
            $(row).find("td.value").attr("orig-type", value.type);
        } else {
            // create new editing row
            $(row).find(".value").removeClass("base").addClass("editing");
            $(row).addClass("added");
        }

        return row;
    }

    var resetValue = function(td) {
        $(td).parent().removeClass("modified").removeClass("deleted");
        $(td).find(".label").html($(td).attr("orig-label"));
        $(td).find(".qname").html($(td).attr("orig-qname"));
        $(td).find(".uri").html($(td).attr("orig-uri"));
        if ($(td).attr("orig-type") === "URI") {
            $(td).find("textarea").val('<' + $(td).attr("orig-uri") + '>');
            wrapURI($(td).find("div.uri"));
        } else {
            $(td).find("textarea").val($(td).attr("orig-uri"));
        }
    }

    // fills in the search results box (passed in as ul)
    var fill_in_results = function(ul, results) {
        $(ul).find("li").detach(); // remove old results

        for (var i in results) {
            var res = results[i];
            var row = $("<li class=\"clearfix\"><div class=\"label\">" + res.label + "</div><div class=\"qname\">" + res.qname + "</div><div class=\"uri\">" + res.uri + "</li>")
            $(ul).append(row);
            $(row).click(function(res) {
                return function() {
                    $(ul).siblings("textarea").val(res.uri);
                    $(ul).siblings("div.label").html(res.label);
                    $(ul).siblings("div.qname").html(res.qname);
                    $(ul).siblings("div.uri").html(res.uri);
                    if (auto_blur) {
                        $(ul).siblings("ul.options").find("li.done a").click();
                        //$(ul).siblings("textarea").blur();
                    }
                };
            }(res));
        }
        $(ul).removeClass("reallyhideme");

        // TODO: scroll bar on results
        
        // TODO: change cancel such that it replaces the values with the orig-* values
    }

    // checks the content of the divs under td to the value, setting label and qname when appropriate
    // also resets the value to the original if value is not defined
    var set_td_value = function(td, value) {
        // get the original uri to compare to value
        var orig = $(td).attr("orig-uri");
        // if value is not defined, reset the value
        if (value == undefined) {
            value = orig;
        }
        // remove surrounding <> from the value if it's a uri
        if (value.match(uri_re)) {
            value = value.substr(1, value.length-2);
        }

        // set the uri to the value
        $(td).children("div.uri").text(value);
        if (!value.indexOf("\"") == 0) {
            wrapURI($(td).find("div.uri"));
        }
        // if the value is not the same as the original do the following
        if (value !== orig) {
            // TODO: we could possibly trigger a search here for uris to find appropriate label and qnames
            $(td).children(".label").html("");
            $(td).children(".qname").html("");
        } else {
            // otherwise reset the label and qname to the original values
            $(td).children(".label").html($(td).attr("orig-label"));
            $(td).children(".qname").html($(td).attr("orig-qname"));
        }
    };

    // sort, but always put rdf:label first and rdf:type second
    var preds = Object.keys(predicateData).sort(function(a,b) {
        if (a === b) {
            return 0;
        }
        if (a === "http://www.w3.org/1999/02/22-rdf-syntax-ns#type") {
            if (b === "http://www.w3.org/2000/01/rdf-schema#label") {
                return 1;
            } else {
                return -1;
            }
        } else if (a === "http://www.w3.org/2000/01/rdf-schema#label") {
            return -1;
        } else if (b === "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" || b === "http://www.w3.org/2000/01/rdf-schema#label") {
            return 1;
        }
        return a > b ? 1 : -1;
    });

    // build the properties table
    for (var pred in preds) {
        pred = preds[pred];
        var predicate = {'uri': pred, 'qname': predicateData[pred].qname, 'label': predicateData[pred].label}
        $("<tbody>").insertBefore($("tbody.options")).attr("data-predicate", pred);
        for (var i in predicateData[pred].value) {
            var val = predicateData[pred].value[i];
            var value = val.value;
            if (val.type === "Literal") {
                value = '"' + val.value + '"';
                if (val.language) {
                    value += "@" + val.language;
                }
                if (val.datatype) {
                    value += "^^" + val.datatype;
                }
            }
            var row = newRow(predicate, {'uri': value, 'qname': val.qname, 'label': val.label, 'type': val.type})
                .appendTo($("#properties tbody[data-predicate='" + predicate.uri + "']"));
            if (val['class']) {
                $(row).addClass(val['class']);
                if (pred === "http://www.w3.org/2000/01/rdf-schema#label" && value === "\"\"") {
                        $(row).find(".value").removeClass("base").addClass("editing");
                } else if (pred === "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" && value === "") {
                    $(row).find(".value").removeClass("base").addClass("editing");
                }
            }
        }
    }

    // sets up the buttons for each row
    var setup_buttons = function(root) {

        // set up editing links
        $(root).find("td li a").click(function() {
            return false; // stop the browser from following the anchor
        });

        // clicking "change" puts an element in "editing" mode
        $(root).find("td li.change a").click(function() {
            var p = $(this).closest("td");
            $(p).removeClass("base").addClass("editing");
            // store old values
            $(p).attr("last-label", $(p).children("div.label").html());
            $(p).attr("last-qname", $(p).children("div.qname").html());
            $(p).attr("last-uri", $(p).children("div.uri a").text() || $(p).children("div.uri").text());
            // disable "Store" button
            $("button#submitresource").prop("disabled", true);
        });

        // clicking "cancel" returns the element to "base" mode, and resets the editing widgets
        $(root).find("td li.cancel a").click(function() {
            var p = $(this).closest("td");
            $(p).removeClass("editing").addClass("base");
            // restore old values
            var label = $(p).attr("last-label");
            if (label == undefined) {
                label = "";
            }
            var qname = $(p).attr("last-qname");
            if (qname == undefined) {
                qname = "";
            }
            var uri = $(p).attr("last-uri");
            if (uri == undefined) {
                uri = "\"\"";
            }
            $(p).find("div.label").html(label);
            $(p).find("div.qname").html(qname);
            $(p).find("div.uri").text(uri);
            if (!uri.indexOf("\"") == 0) {
                wrapURI($(p).find("div.uri"));
            }
            $(p).find("textarea").val(uri);
        });

        // clicking "done" returns the element to "base" mode, and sets the value to the editing widget's value
        // updating the row's status if the value was modified
        $(root).find("td li.done a").click(function() {
            var p = $(this).closest("td");
            $(p).removeClass("editing").addClass("base");
            var val = $(p).find("textarea").val();
            if (val.match(uri_re)) {
                val = val.substr(1, val.length-2);
            }
            var orig = $(p).attr("orig-uri");
            if (val === orig) {
                resetValue($(p));
            } else {
                if (!$($(p)).parent().hasClass("added")) {
                    $($(p)).parent().addClass("modified");
                }
                // TODO: trigger a search event to fill in label, qname and uri
                // if they're not already set
            }
            if ($(p).is(".property")) {
                // if this is a change to the property set the values for all the other rows for this property
                $(p).parent().siblings().find("td.property").each(function() {
                    $(this).find("div.label").html($(p).find("div.label").html());
                    $(this).find("div.qname").html($(p).find("div.qname").html());
                    $(this).find("div.uri").html($(p).find("div.uri").html());
                    $(this).find("textarea").val($(p).find("textarea").val());
                });
            }
        });

        // clicking "reset" resets any changes made to the state they were in when the page loaded
        $(root).find("td li.reset a").click(function() {
            resetValue($(this).closest("td"));
        });

        // clicking "delete" marked the item as deleted or in the case of added rows, removes it completely
        $(root).find("td li.delete a").click(function() {
            if ($(this).closest("tr").hasClass("added")) {
                $(this).closest("tr").detach();
            } else {
                $(this).closest("tr").addClass("deleted").removeClass("modified");
            }
        });

        // clicking "add" ......
        $(root).find("td li.add a").click(function() {
            var x = $(this).closest("tr").find("td");
            x = {'label': x.find("div.label").html(),
                 'qname': x.find("div.qname").html(),
                 'uri': x.find("div.uri").html()};
            setup_buttons($(newRow(x)).appendTo($(this).closest("tbody")));
            $("button#submitresource").prop("disabled", true);
        });

        // clicking "literal" checks if the value is a literal, and if not wraps it with \"\"
        $(root).find("td li.literal a").click(function() {
            var p = $(this).closest("td");
            var val = $(p).find("textarea").val();
            if (!val.match(literal_re)) {
                val = "\"" + val + "\"";
                $(p).find("textarea").val(val);
                set_td_value($(p), val);
            }
        });


        // setup search for textareas
        $(root).find("textarea").each(function() {
            var ta = $(this);
            var p = $(this).closest("td");
            var orig = $(p).attr("orig-uri");
            var interval = null;
            var last_term = null;
            var last_results = [];
            $(ta)
                .blur(function() {
                    if (auto_blur && $(this).siblings("ul.search-results").is(".reallyhideme")) {
                        // only call this if the search results window is closed
                        $(this).siblings("ul.options").find("li.done a").click();
                    }
                })
                .keydown(function() {
                    clearInterval(interval);
                })
                .keyup(function(a) {
                    clearInterval(interval);
                    if (a.keyCode == 27) {
                        return;
                    }
                    var term = $(ta).val();
                    set_td_value(p, term);
                    // remove surrounding <> from the value if it's a uri
                    if (term.match(uri_re)) {
                        term = term.substr(1, term.length-2);
                    }
                    interval = setTimeout(function () {
                        // don't search if "Literal"
                        if (term.indexOf("\"") == 0) {
                            return;
                        }

                        // don't trigger the ajax call again if the new term is an extention
                        // of the last searched for term
                        // TODO: client-side filtering of the last_term results when
                        // term.indexOf(last_term) >= 0
                        if (last_term == null || term !== last_term) {
                            $.ajax({
                                type: 'GET',
                                url: window.FLASK_ROOT_URL+"/search",
                                data: {
                                    "term": term,
                                    "type": $(p).is(".property") ? "predicates" : "all",
                                    "custom": false
                                },
                                dataType: "json",
                                success: function(data) {
                                    last_term = term;
                                    last_results = data;
                                    // fill in search results
                                    fill_in_results($(ta).siblings(".search-results"), data);
                                },
                                error: function(msg) {
                                    console.log(msg);
                                },
                                complete: function() {
                                }
                            });
                        } else {
                            // TODO: filter last_results with new terms
                            console.log("filtering previous results");
                            fill_in_results($(ta).siblings(".search-results"), last_results);
                        }
                    }, 500);
                });
        });

        // trigger edit mode when td is double clicked
        $(root).find("td.property, td.value").dblclick(function() {
            $(this).find("li.change a").click();
            // focus the textarea so that clicking away from it closes it (using autoblur)
            $(this).find("textarea").focus();
        });
        
    };

    setup_buttons($("table.properties"));

    // "add predicate" button
    $("#addpredicate").click(function() {
        var tb = $("<tbody>");
        tb.insertBefore($("tbody.options"));
        setup_buttons($(newRow()).appendTo($(tb)));
        $("button#submitresource").prop("disabled", true);
    });

    $("#resuri a.change").click(function() {
        $("#resuri").addClass("editing");
    });

    // URI editing
    $("#resuri > button.set").click(function() {
        var val = $("#resuri input").val();
        var old = $("#resuri").attr("orig");
        if (val !== old) {
            $("#resuri").addClass("changed");
        }
        $("#properties table").attr("data-subject", val);
        $("#resuri > span.uri").text(val);
        $("#resuri").removeClass("editing");
    });

    $("#resuri > button.cancel").click(function() {
        $("#resuri").removeClass("editing");
        $("#resuri input").val($("#resuri > span.uri").text());
    });

    $("#resuri a.reset").click(function() {
        $("#resuri").removeClass("changed");
        var orig = $("#resuri").attr("orig");
        $("#properties table").attr("data-subject", orig);
        $("#resuri > span.uri").text(orig);
        $("#resuri input").val(orig);
    });

    // sanity check the values to make sure everything is good
    var sanitycheck = function() {

        // TODO: do something useful with errors
        var ok = true;
        var errors = []

        // make sure URI is set to something other than the "context"
        var ctx = $("p#resuri").attr("data-context");
        var val = $("#resuri input").val();
        // TODO: more detailed URI checking
        if (ctx === val || val === "") {
            //$("#resuri").addClass("error");
            errors.push("invalid URI");
            ok = false;
        }

        if ($("td.editing").length != 0) {
            errors.push("some properties are still in editing mode");
            ok = false;
        }

        // check the values of each predicate
        $("#properties table td.property").each(function() {
            var pred = $(this).find("div.uri").text();
            var v = $(this).siblings(".value");
            v = $(v).find("div.uri a").text() || $(v).find("div.uri").text();
            if (pred === "http://www.w3.org/2000/01/rdf-schema#label" || pred === "http://www.w3.org/1999/02/22-rdf-syntax-ns#type") {
                // make sure "label" and "type" have values
                if (v === "" || v.indexOf("\"\"") == 0) {
                    ok = false;
                    //$(this).parent().addClass("error");
                    errors.push("label must not be an empty string");
                }
            }
            if (v === "") {
                // no value has been set
                ok = false;
                //$(this).parent().addClass("error");
                errors.push("no value set for " + pred);
            } else if (v[0] == '"' && !v.match(literal_re)) {
                ok = false;
                //$(this).parent().addClass("error");
                errors.push("invalid literal for " + pred);
            }
        });
        if (errors.length > 0) {
            console.log(errors);
        }
        return ok;
    };

    // "Store" button
    $("#submitresource").click(function() {
        // do sanity tests on values
        if (!sanitycheck()) {
            return false;
        }
        var diff = generate_diff();
        $(this).siblings("input[name='uri']").val($("#properties table").attr("data-subject"));
        $(this).siblings("input[name='diff']").val(JSON.stringify(diff));
        return true;
    });
    
    // general clicks and key presses
    $("body").click(function() {
        // close search windows
        $(".search-results").addClass("reallyhideme");
    }).keyup(function(a) {
        if (a.keyCode == 27) { // esc key
            $(".search-results").addClass("reallyhideme");
        }
    }).mousemove(function() {
        // TODO: mouse move may be overkill.....
        if (sanitycheck()) {
            $("button#submitresource").prop("disabled", false);
        } else {
            $("button#submitresource").prop("disabled", true);
        }
    });
}
