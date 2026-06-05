import { useState, useEffect } from "react";
import {
	BrowserRouter as Router,
	Routes,
	Route,
	Navigate,
} from "react-router-dom";
import CollectionPage from "./pages/CollectionPage";
import ProfilePage from "./pages/ProfilePage";
import ProfileWishlistPage from "./pages/ProfileWishlistPage";
import AddShirtFormPage from "./pages/AddShirtFormPage";
import EditShirtFormPage from "./pages/EditShirtFormPage";
import EditProfilePage from "./pages/EditProfilePage";
import HistoryPage from "./pages/HistoryPage";
import GroupsPage from "./pages/GroupsPage";
import KitVariantsPage from "./pages/KitVariantsPage";
import KitDetailPage from "./pages/KitDetailPage";
import MessagesPage from "./pages/MessagesPage";
import FeedPage from "./pages/FeedPage";
import NavBar from "./components/NavBar";
import api, {
	getUnreadMessagesCount,
	getNotificationsUnreadCount,
} from "./services/api";

import ScrollToTop from "./components/utils/ScrollTop";
import "./index.css";

const AuthGate = ({ authLoading, user, children }) => {
	if (authLoading) {
		return (
			<div className="container py-5">
				<div className="d-flex justify-content-center align-items-center py-5">
					<div className="spinner-border text-primary" role="status" />
				</div>
			</div>
		);
	}

	if (!user) {
		return <Navigate to="/" replace />;
	}

	return children;
};

function App() {
	const [user, setUser] = useState(null); // User state
	const [authLoading, setAuthLoading] = useState(true);
	const [unreadMessagesCount, setUnreadMessagesCount] = useState(0);
	const [unreadNotificationsCount, setUnreadNotificationsCount] = useState(0);

	const fetchUserData = async ({ clearAuthOnError = true } = {}) => {
		try {
			const response = await api.get("/auth/user/");
			setUser(response.data);
			return response.data;
		} catch (error) {
			console.error("Błąd pobierania profilu:", error);
			setUser(null);
			if (clearAuthOnError) {
				localStorage.removeItem("access_token");
				localStorage.removeItem("refresh_token");
			}
			return null;
		} finally {
			setAuthLoading(false);
		}
	};

	useEffect(() => {
		const token = localStorage.getItem("access_token");
		if (token) {
			fetchUserData();
			return;
		}

		setAuthLoading(false);
	}, []);

	useEffect(() => {
		if (!user) {
			setUnreadMessagesCount(0);
			setUnreadNotificationsCount(0);
			return;
		}

		refreshUnreadMessagesCount();
		refreshUnreadNotificationsCount();

		const intervalId = window.setInterval(() => {
			refreshUnreadMessagesCount();
			refreshUnreadNotificationsCount();
		}, 30000);

		return () => window.clearInterval(intervalId);
	}, [user]);
	const handleLoginSuccess = () => {
		setAuthLoading(true);
		fetchUserData();
	};

	const handleLogout = () => {
		localStorage.removeItem("access_token");
		localStorage.removeItem("refresh_token");
		setUser(null);
		setAuthLoading(false);
		setUnreadMessagesCount(0);
		setUnreadNotificationsCount(0);
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

	const refreshUnreadNotificationsCount = async () => {
		const token = localStorage.getItem("access_token");
		if (!token) {
			setUnreadNotificationsCount(0);
			return;
		}

		try {
			const data = await getNotificationsUnreadCount();
			setUnreadNotificationsCount(data.unread_count || 0);
		} catch (error) {
			console.error("Failed to load unread notifications count:", error);
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
						unreadNotificationsCount={unreadNotificationsCount}
						refreshUnreadNotificationsCount={refreshUnreadNotificationsCount}
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
							<AuthGate authLoading={authLoading} user={user}>
								<ProfilePage user={user} />
							</AuthGate>
						}
					/>

					{/* User Profile Page */}
					<Route
						path="/profile/:username"
						element={<ProfilePage user={user} />}
					/>
					<Route
						path="/profile/:username/wishlist"
						element={<ProfileWishlistPage user={user} />}
					/>
					<Route
						path="/profile/:username/kits/:kitId"
						element={<KitDetailPage user={user} />}
					/>
					<Route
						path="/messages"
						element={
							<AuthGate authLoading={authLoading} user={user}>
								<MessagesPage
									user={user}
									refreshUnreadMessagesCount={refreshUnreadMessagesCount}
								/>
							</AuthGate>
						}
					/>
					<Route
						path="/messages/:conversationId"
						element={
							<AuthGate authLoading={authLoading} user={user}>
								<MessagesPage
									user={user}
									refreshUnreadMessagesCount={refreshUnreadMessagesCount}
								/>
							</AuthGate>
						}
					/>
					<Route
						path="/feed"
						element={
							<AuthGate authLoading={authLoading} user={user}>
								<FeedPage user={user} />
							</AuthGate>
						}
					/>

					{/* Edit Profile Page */}
					<Route
						path="/profile/edit"
						element={
							<AuthGate authLoading={authLoading} user={user}>
								<EditProfilePage
									user={user} // User logged in
									setUser={setUser} // Function to update user state
								/>
							</AuthGate>
						}
					/>

					{/* Add Shirt Form Page */}
					<Route
						path="/add-kit"
						element={
							<AuthGate authLoading={authLoading} user={user}>
								<AddShirtFormPage />
							</AuthGate>
						}
					/>

					{/* Edit Shirt Form Page */}
					<Route
						path="/edit-kit/:id"
						element={
							<AuthGate authLoading={authLoading} user={user}>
								<EditShirtFormPage user={user} />
							</AuthGate>
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
