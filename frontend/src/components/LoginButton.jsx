import { useGoogleLogin } from "@react-oauth/google";
import { useTranslation } from "react-i18next";
import api from "../services/api";

const LoginButton = ({ onLoginSuccess }) => {
	const { t } = useTranslation();

	const login = useGoogleLogin({
		onSuccess: async (tokenResponse) => {
			try {
				const res = await api.post("/auth/google/", {
					access_token: tokenResponse.access_token,
				});

				const { access, refresh } = res.data;
				localStorage.setItem("access_token", access);
				localStorage.setItem("refresh_token", refresh);
				onLoginSuccess();

			} catch (err) {
				console.error("Login Error:", err.response?.data || err.message);
				alert(t("common.loginFailed"));
			}
		},
		onError: () => console.log("Login Failed"),
	});

	return (
		<button onClick={() => login()} className="btn btn-outline-dark">
			{t("nav.loginWithGoogle")}
		</button>
	);
};

export default LoginButton;
