/* data should be map {results: [{id:0,tag:'enhancement'}]} */

function gen_query_for_custom_entry() {
    var text = function (item) { return ""+item.text; };
    return function (query) {
         var data = this.data;
         var t = query.term, filtered = { results: [] }, process;
         if (t === "") {
             query.callback({results: data});
             return;
         }

         process = function(datum, collection) {
             var group, attr;
             datum = datum[0];
             if (datum.children) {
                 group = {};
                 for (attr in datum) {
                     if (datum.hasOwnProperty(attr)) group[attr]=datum[attr];
                 }
                 group.children=[];
                 $(datum.children).each2(function(i, childDatum) { process(childDatum, group.children); });
                 if (group.children.length) {
                     collection.push(group);
                 }
             } else {
                 if (query.matcher(t, text(datum))) {
                     collection.push(datum);
                 }
             }
         };

         $(data).each2(function(i, datum) { process(datum, filtered.results); });

         if (filtered.results.length == 0) {
             filtered.results = [{text:"custom input", children:[{id: query.term, text: query.term}]}];
         }

         query.callback(filtered);
    }
}

(function ($) {
    $.fn.select2helper = function(default_value, type, result_parser, allowCustom) {
        default_value = default_value || '';
        allowCustom = allowCustom || false;
        type = type || 'all';
        result_parser = result_parser || function(data, page) {
            var res = []
            for (var i in data.results) {
                if (typeof(data.results[i]) === "object") {
                    res.push(data.results[i]);
                } else {
                    res.push({id:data.results[i], text: data.results[i]});
                }
            }
            return res;
        }
        return $(this).select2({
            //query: gen_query_for_custom_entry(),
            //data: objectData,
            minimumInputLength: 1,
            ajax: {
                url: "/ajax/search",
                dataType: "json",
                quietMillis: 1000,
                data: function(term, page) {
                    return {
                        term: term,
                        type: type,
                        custom: allowCustom
                    };
                },
                results: function(data, page) {
                    res = result_parser(data, page);
                    return {results: res};
                }
            },
            placeholder: "Select a value or enter a new one...",
            initSelection: function(element, callback) {
                if (typeof(default_value) === "object") {
                    callback(default_value);
                } else {
                    callback({id:default_value, text:default_value});
                }
            },
            allowClear: true
        });
    }
}(jQuery));
