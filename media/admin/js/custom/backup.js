var $ = django.jQuery;
var weekdayNames = new Array('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday');

$(document).ready(function() {
    $("ul.breadcrumb>li.active").text("System Dashboard");

    $("#content").addClass("row").removeClass("row-fluid").removeClass("colM");
    $("#content>h2.content-title").remove();
    $("span.divider").remove();
    $("lspan").remove();

    $.ajax({
        url : "/site_data/stat_backup.txt",
        dataType: "text",
        success : function (data) {
            var txt = data.split(/\t/);

            $("#id_news_n").html('<i>' + txt[0] + '</i>');
            $("#id_news_s").html('<span style="color:#00f;">' + txt[1] + '</span>');
            $("#id_member_n").html('<i>' + txt[2] + '</i>');
            $("#id_member_s").html('<span style="color:#00f;">' + txt[3] + '</span>');
            $("#id_pub_n").html('<i>' + txt[4] + '</i>');
            $("#id_pub_s").html('<span style="color:#00f;">' + txt[5] + '</span>');
            $("#id_rot_n").html('<i>' + txt[6] + '</i>');
            $("#id_rot_s").html('<span style="color:#00f;">' + txt[7] + '</span>');
            $("#id_spe_n").html('<i>' + txt[8] + '</i>');
            $("#id_spe_s").html('<span style="color:#00f;">' + txt[9] + '</span>');

            $("#id_mysql_s").html('<span style="color:#00f;">' + txt[10] + '</span>');
            $("#id_static_s").html('<span style="color:#00f;">' + txt[11] + '</span>');
            $("#id_apache_s").html('<span style="color:#00f;">' + txt[12] + '</span>');
            $("#id_mysql_p").html($("#id_mysql_p").html() + '<br/><code>' + txt[13] + '</code>');
            $("#id_static_p").html($("#id_static_p").html() + '<br/><code>' + txt[14] + '</code>');
            $("#id_apache_p").html($("#id_apache_p").html() + '<br/><code>' + txt[15] + '</code>');

            var gdrive = txt[16].split(/~|~/);
            var names = [], sizes = [], times = [];
            for (var i = 0; i < gdrive.length; i += 12) {
                names.push(gdrive[i+2]);
                sizes.push(gdrive[i+4] + ' ' + gdrive[i+6]);
                times.push(gdrive[i+8] + ' ' + gdrive[i+10]);
            }
            var html = '';
            for (var i = 0; i < names.length; i++) {
                html += '<tr><td><code>' + names[i] + '</code></td><td><span class="label label-primary">' + times[i] + '</span></td><td><span style="color:#00f;">' + sizes[i] + '</span></td></tr>'
            }
            html += '<tr><td></td><td></td><td></td></tr>'
            $("#gdrive_list").html(html);

        }
    });

    $.ajax({
        url : "/admin/backup_form",
        dataType: "json",
        success : function (data) {
            $("#id_time_backup").val(data.time_backup);
            $("#id_day_backup").val(data.day_backup);
            $("#id_time_upload").val(data.time_upload);
            $("#id_day_upload").val(data.day_upload);

            $("#id_time_backup").trigger("change");
            $("#id_time_upload").trigger("change");

            $("#modal_backup").html('On <span class="label label-primary">' + $("#id_time_backup").val() + '</span> every <span class="label label-inverse">' + weekdayNames[$("#id_day_backup").val()] + '</span> (UTC).');
            $("#modal_upload").html('On <span class="label label-primary">' + $("#id_time_upload").val() + '</span> every <span class="label label-inverse">' + weekdayNames[$("#id_day_upload").val()] + '</span> (UTC).');
        }
    });

    $("#id_time_backup, #id_day_backup").on("change", function() {
        var time = $("#id_time_backup").val();
        var backup = new Date(Date.UTC(2000, 0, parseInt($("#id_day_backup").val()) + 2, time.split(':')[0], time.split(':')[1], 0));
        $("#time_backup_pdt").html(backup.toLocaleTimeString());
        $("#day_backup_pdt").html(weekdayNames[backup.getDay()]);
    });
    $("#id_time_upload, #id_day_upload").on("change", function() {
        var time = $("#id_time_upload").val();
        var backup = new Date(Date.UTC(2000, 0, parseInt($("#id_day_upload").val()) + 2, time.split(':')[0], time.split(':')[1], 0));
        $("#time_upload_pdt").html(backup.toLocaleTimeString());
        $("#day_upload_pdt").html(weekdayNames[backup.getDay()]);
    });


    


});
