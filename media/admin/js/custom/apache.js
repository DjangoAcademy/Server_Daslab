var $ = django.jQuery;

function get_apache_stat() {
    $.ajax({
        url : "/admin/apache_stat",
        dataType: "json",
        success : function (data) {
            console.log(data);

            $("#apache_title").html(data['title']);
            $("#apache_ver").html(data['ver_apache']);
            $("#apache_wsgi").html(data['ver_wsgi']);
            $("#apache_python").html(data['ver_python']);
            $("#apache_mpm").html(data['mpm']);
            $("#apache_port").html(data['port']);

            $("#apache_build_time").html(data['time_build']);
            $("#apache_current_time").html(data['time_current']);
            $("#apache_restart_time").html(data['time_restart']);
            $("#apache_up_time").html(data['time_up']);

            var server_load = data['server_load'].split(/\//);
            $("#apache_server_load").html('<span style="color:#f00;">' + server_load[0] + '</span> | <span style="color:#080;">' + server_load[1] + '</span> | <span style="color:#00f;">' + server_load[2] + '</span>');
            var cpu_usage = data['cpu_usage'].split(/\//);
            $("#apache_cpu_usage").html('<i>u</i> <span style="color:#f00;">' + cpu_usage[0] + '</span> | <i>s</i> <span style="color:#080;">' + cpu_usage[1] + '</span> | <i>cu</i> <span style="color:#00f;">' + cpu_usage[2] + '</span> | <i>cs</i> <span style="color:#f80;">' + cpu_usage[3] + '</span>');
            var traffic = data['traffic'].split(/\//);
            $("#apache_traffic").html('<span style="color:#f00;">' + traffic[0] + '</span> <i>req/s</i> | <span style="color:#080;">' + traffic[1] + '</span> <i>B/s</i> | <span style="color:#00f;">' + traffic[2] + '</span> <i>kB/req</i>');
            $("#apache_total_access").html(data['total_access']);
            $("#apache_total_traffic").html('<span style="color:#00f">' + data['total_traffic'] + '</span>');
            $("#apache_cpu_load").html(data['cpu_load'] + '%');

            $("#apache_process").html(data['processing']);
            $("#apache_idle").html(data['idle']);
            $("#apache_worker").html(data['worker']);

            $("#apache_client").html(data['table']);
        },  
    });
}

$(document).ready(function() {
    $("[data-toggle='popover']").popover({trigger: "hover"});
    $("[data-toggle='tooltip']").tooltip();
    $("ul.breadcrumb").append('<li class="active"><a href="/admin/apache/">Apache Status</a></li>');

    get_apache_stat();
    setInterval(function () { get_apache_stat();}, 3000);

});
