callback: function (data) {
    if(data.status === 'success'){
        $('#donation-form').find('input[type="text"]').val('');
        $('#donation-form').find('select').val('0');
        $.ajax({
            url: '{%url ''%}',
            data: JSON.stringify(data)
        });
    }
    console.log(data);
},