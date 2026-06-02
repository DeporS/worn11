import { useState, useEffect } from "react";
import {
	BrowserRouter as Router,
	Routes,
	Route,
	Navigate,
} from "react-router-dom";
import CollectionPage from "./pages/CollectionPage";
import ProfilePage from "./pages/ProfilePage";
import AddShirtFormPage from "./pages/AddShirtFormPage";
import EditShirtFormPage from "./pages/EditShirtFormPage";
import EditProfilePage from "./pages/EditProfilePage";
import HistoryPage from "./pages/HistoryPage";
import GroupsPage from "./pages/GroupsPage";
import KitVariantsPage from "./pages/KitVariantsPage";
import KitDetailPage from "./pages/KitDetailPage";
import MessagesPage from "./pages/MessagesPage";
import NavBar from "./components/NavBar";
import api, { getUnreadMessagesCount } from "./services/api";

import ScrollToTop from "./components/utils/ScrollTop";
import "./index.css";

function App() {
	const [user, setUser] = useState(null); // User state
	const [unreadMessagesCount, setUnreadMessagesCount] = useState(0);

	const fetchUserData = async () => {
		try {
			const response = await api.get("/auth/user/");
			setUser(response.data);
		} catch (error) {
			console.error("Błąd pobierania profilu:", error);
			handleLogout();
		}
	};

	useEffect(() => {
		const token = localStorage.getItem("access_token");
		if (token) {
			fetchUserData();
		}
	}, []);

	useEffect(() => {
		if (!user) {
			setUnreadMessagesCount(0);
			return;
		}

		refreshUnreadMessagesCount();

		const intervalId = window.setInterval(() => {
			refreshUnreadMessagesCount();
		}, 30000);

		return () => window.clearInterval(intervalId);
	}, [user]);
	const handleLoginSuccess = () => {
		fetchUserData();
	};

	const handleLogout = () => {
		localStorage.removeItem("access_token");
		localStorage.removeItem("refresh_token");
		setUser(null);
		setUnreadMessagesCount(0);
	};

	const refreshUnreadMessagesCount = async () => {
		const token = localStorage.getItem("access_token");
		if (!token) {
			setUnreadMessagesCount(0);
			return;
		}

		try {
			const data = await getUnreadMessagesCount();
			setUnreadMessagesCount(data.unread_count || 0);
		} catch (error) {
			console.error("Failed to load unread messages count:", error);
		}
	};

	return (
		<Router>
			<div>
				<div className="sticky-top">
					<NavBar
						user={user}
						onLoginSuccess={handleLoginSuccess}
						onLogout={handleLogout}
						refreshUser={fetchUserData}
						unreadMessagesCount={unreadMessagesCount}
					/>
				</div>

				<ScrollToTop />

				<Routes>
					{/* Landing Page */}
					<Route path="/" element={<CollectionPage user={user} />} />

					{/* My Collection Page */}
					<Route
						path="/my-collection"
						element={
							user ? (
								<ProfilePage user={user} />
							) : (
								<Navigate to="/" />
							)
						}
					/>

					{/* User Profile Page */}
					<Route
						path="/profile/:username"
						element={<ProfilePage user={user} />}
					/>
					<Route
						path="/profile/:username/kits/:kitId"
						element={<KitDetailPage user={user} />}
					/>
					<Route
						path="/messages"
						element={
							user ? (
								<MessagesPage
									user={user}
									refreshUnreadMessagesCount={refreshUnreadMessagesCount}
								/>
							) : (
								<Navigate to="/" />
							)
						}
					/>
					<Route
						path="/messages/:conversationId"
						element={
							user ? (
								<MessagesPage
									user={user}
									refreshUnreadMessagesCount={refreshUnreadMessagesCount}
								/>
							) : (
								<Navigate to="/" />
							)
						}
					/>

					{/* Edit Profile Page */}
					<Route
						path="/profile/edit"
						element={
							<EditProfilePage
								user={user} // User logged in
								setUser={setUser} // Function to update user state
							/>
						}
					/>

					{/* Add Shirt Form Page */}
					<Route
						path="/add-kit"
						element={
							user ? <AddShirtFormPage /> : <Navigate to="/" />
						}
					/>

					{/* Edit Shirt Form Page */}
					<Route
						path="/edit-kit/:id"
						element={
							user ? (
								<EditShirtFormPage user={user} />
							) : (
								<Navigate to="/" />
							)
						}
					/>

					{/* History Page */}
					<Route
						path="/history"
						element={<HistoryPage user={user} />}
					/>

					{/* Groups Page */}
					<Route
						path="/groups"
						element={<GroupsPage user={user} />}
					/>

					{/* Kit Variants Page */}
					<Route
						path="/history/team/:teamIdentifier/variants"
						element={<KitVariantsPage user={user} />}
					/>
				</Routes>
			</div>
		</Router>
	);
}

export default App;
