class MockUser:

    def __init__(self):
        self.username = 'testuser'
        self.password1 = 'pa@55worD'
        self.password2 = 'pa@55worD'
        self.email = 'testuser@example.com'
        self.first_name = 'Ben'
        self.last_name = 'Buffer'
        self.phone_number = '080276352615'
        self.state_of_residence = 'ABIA'

    @property
    def spawn(self):
        return {
            'username': self.username,
            'password1': self.password1,
            'password2': self.password2,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone_number': self.phone_number,
            'state_of_residence': self.state_of_residence,
        }
