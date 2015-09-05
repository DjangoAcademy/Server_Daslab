var $ = django.jQuery;
var weekdayNames = new Array('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday');

$(document).ready(function() {
  $("ul.breadcrumb > li.active").text("System Dashboard");

  $("#content").addClass("row").removeClass("row-fluid").removeClass("colM");
  $("#content > h2.content-title").remove();
  $("span.divider").remove();
  $("lspan").remove();

  $.ajax({
        url : "/site_data/stat_sys.txt",
        dataType: "text",
        success : function (data) {
        	var txt = data.split(/\t/);

        	$("#id_linux").html(txt[0]);
        	$("#id_python").html(txt[1]);
        	$("#id_django").html(txt[2]);
        	$("#id_django_suit").html(txt[3]);
        	$("#id_django_adminplus").html(txt[4]);
            $("#id_django_crontab").html(txt[5]);
            $("#id_django_environ").html(txt[6]);
            $("#id_django_filemanager").html(txt[7]);
        	$("#id_jquery").html(txt[8]);
        	$("#id_bootstrap").html(txt[9]);
            $("#id_swfobj").html(txt[10]);
            $("#id_fullcal").html(txt[11]);
            $("#id_moment").html(txt[12]);
        	$("#id_mysql").html(txt[13]);
        	$("#id_apache").html(txt[14]);
        	$("#id_webauth").html(txt[15]);
        	$("#id_ssh").html(txt[16]);
        	$("#id_git").html(txt[17]);
            $("#id_git_inspector").html(txt[18]);
            $("#id_gdrive").html(txt[19]);
            $("#id_pandoc").html(txt[20]);
            $("#id_curl").html(txt[21]);
        	$("#id_pip").html(txt[22]);
        	$("#id_virtualenv").html(txt[23]);
            $("#id_boto").html(txt[24]);
            $("#id_simplejson").html(txt[25]);
            $("#id_gviz").html(txt[26]);
            $("#id_nano").html(txt[27]);

        	var disk_sp = txt[28].split(/\//);
            $("#id_disk_space > div > div.progress-bar-success").css("width", (parseInt(disk_sp[0]) / (parseInt(disk_sp[0]) + parseInt(disk_sp[1])) * 100).toString() + '%' ).html(disk_sp[0]);
            $("#id_disk_space > div > div.progress-bar-danger").css("width", (parseInt(disk_sp[1]) / (parseInt(disk_sp[0]) + parseInt(disk_sp[1])) * 100).toString() + '%' ).html(disk_sp[1]);
        	var mem_sp = txt[29].split(/\//);
            $("#id_memory > div > div.progress-bar-success").css("width", (parseInt(mem_sp[0]) / (parseInt(mem_sp[0]) + parseInt(mem_sp[1])) * 100).toString() + '%' ).html(mem_sp[0]);
            $("#id_memory > div > div.progress-bar-danger").css("width", (parseInt(mem_sp[1]) / (parseInt(mem_sp[0]) + parseInt(mem_sp[1])) * 100).toString() + '%' ).html(mem_sp[1]);

        	$("#id_backup").html('<span style="color:#00f;">' + txt[30] + '</span>');
        	var cpu = txt[31].split(/\//);
        	$("#id_cpu").html('<span style="color:#f00;">' + cpu[0] + '</span> | <span style="color:#080;">' + cpu[1] + '</span> | <span style="color:#00f;">' + cpu[2] + '</span>');

            $("#id_base_dir").html('<code>' + txt[32] + '</code>');
            $("#id_media_root").html('<code>' + txt[33] + '</code>');
            $("#id_static_root").html('<code>' + txt[34] + '</code>');
    	}
    });

    $.ajax({
        url : "/admin/backup_form",
        dataType: "json",
        success : function (data) {
            $("#id_week_backup").html($("#id_week_backup").html() + '<br/>On <span class="label label-primary">' + data.time_backup + '</span> every <span class="label label-inverse">' + weekdayNames[data.day_backup] + '</span> (UTC)');
            $("#id_week_upload").html($("#id_week_upload").html() + '<br/>On <span class="label label-primary">' + data.time_upload + '</span> every <span class="label label-inverse">' + weekdayNames[data.day_upload] + '</span> (UTC)');

            if (data.time_backup) {
                $("#id_week_backup_stat").html('<p class="lead"><span class="label label-green"><span class="glyphicon glyphicon-ok-sign"></span></span></p>');
            } else {
                $("#id_week_backup_stat").html('<p class="lead"><span class="label label-danger"><span class="glyphicon glyphicon-remove-sign"></span></span></p>');
            }
            if (data.time_upload) {
                $("#id_week_upload_stat").html('<p class="lead"><span class="label label-green"><span class="glyphicon glyphicon-ok-sign"></span></span></p>');
            } else {
                $("#id_week_upload_stat").html('<p class="lead"><span class="label label-danger"><span class="glyphicon glyphicon-remove-sign"></span></span></p>');
            }
        }
    });

});
