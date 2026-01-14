const API_URL = 'http://127.0.0.1:8000';

const UserAvatar = ({ user, size = 35 }) => {
    const avatarUrl = user?.avatar || user?.profile?.avatar;

    const getAvatarUrl = (path) => {
        if (!path) return null;
        if (path.startsWith('http')) return path;
        return `${API_URL}${path}`;
    };

    if (avatarUrl) {
        return (
            <img
                src={getAvatarUrl(avatarUrl)}
                alt="Avatar"
                className="rounded-circle border"
                style={{ width: size, height: size, objectFit: 'cover' }}
            />
        );
    }

    return (
        <div
            className="bg-primary text-white rounded-circle d-flex justify-content-center align-items-center fw-bold"
            style={{ width: size, height: size, fontSize: size * 0.4 }}
        >
            {user.username.charAt(0).toUpperCase()}
        </div>
    );
};

export default UserAvatar;
