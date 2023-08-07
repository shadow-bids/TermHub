/* https://reactjs.org/docs/hooks-intro.html
https://mui.com/material-ui/react-list/
https://mui.com/material-ui/getting-started/usage/
https://github.com/mui/material-ui
https://stackoverflow.com/questions/53219113/where-can-i-make-api-call-with-hooks-in-react
might be useful to look at https://mui.com/material-ui/guides/composition/#link
referred to by https://stackoverflow.com/questions/63216730/can-you-use-material-ui-link-with-react-router-dom-link
*/
import React from "react";
import {
  // Link, useHref, useParams, BrowserRouter, redirect,
  Outlet,
  Navigate,
  useLocation,
  createSearchParams,
  Routes,
  Route,
} from "react-router-dom";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import "./App.css";
import { isEmpty } from "lodash";

import { ConceptSetsPage } from "./components/Csets";
import { CsetComparisonPage } from "./components/CsetComparisonPage";
import { AboutPage } from "./components/AboutPage";
import { ConceptGraph } from "./components/ConceptGraph";
import {ViewCurrentState, } from "./state/State";
import {CodesetIdsProvider, AlertsProvider, useAlerts, useAlertsDispatch, NewCsetProvider, } from "./state/AppState";
import {SearchParamsProvider, useSearchParamsState} from "./state/SearchParamsProvider";
import {DataGetterProvider} from "./state/DataGetter";
import { UploadCsvPage } from "./components/UploadCsv";
// import { DownloadJSON } from "./components/DownloadJSON";
import MuiAppBar from "./components/MuiAppBar";
import {DataCacheProvider} from "./state/DataCache";
import {AlertMessages} from "./components/AlertMessages";

/* structure is:
    <BrowserRouter>                 // from index.js root.render
      <SearchParamsProvider>        // gets state from query string -- mainly codeset_ids
        <AlertsProvider>
          <NewCsetProvider>
            <DataCacheProvider>       // ability to save to and retrieve from cache in localStorage
              <DataGetterProvider>    // utilities for fetching data. dataCache needs access to this a couple of times
                                      //  so those method calls will have to pass in a dataGetter
                <RoutesContainer/>
              </DataGetterProvider>
            </DataCacheProvider>
          </NewCsetProvider>
        </AlertsProvider>
      </SearchParamsProvider>
    </BrowserRouter>
*/
function QCProvider() {
  // prefetch({itemType: 'all_csets'});
  return (
    // <React.StrictMode> // {/* StrictMode helps assure code goodness by running everything twice, but it's annoying*/}
      <SearchParamsProvider>
        <AlertsProvider>
          <CodesetIdsProvider>
            <NewCsetProvider>
              <DataCacheProvider>
                <DataGetterProvider>
                  <RoutesContainer/>
                </DataGetterProvider>
              </DataCacheProvider>
            </NewCsetProvider>
          </CodesetIdsProvider>
        </AlertsProvider>
      </SearchParamsProvider>
    // </React.StrictMode>
  );
}
function RoutesContainer() {
  const spState = useSearchParamsState();
  const {sp} = spState;
  const {codeset_ids, } = sp;
  const location = useLocation();

  if (sp.sstorage) {
    sessionStorage = JSON.parse(sp.sstorage);
    spState.removeItem('sstorage');
  }
  if (location.pathname === "/") {
    return <Navigate to="/OMOPConceptSets" />;
  }
  if (location.pathname === "/cset-comparison" && isEmpty(codeset_ids)) {
    return <Navigate to="/OMOPConceptSets" />;
  }
  if (location.pathname === "/testing") {
    const test_codeset_ids = [400614256, 411456218, 419757429, 484619125];
    let params = createSearchParams({ codeset_ids: test_codeset_ids });
    // setSearchParams(params);
    let url = "/cset-comparison?" + params;
    // return redirect(url); not exported even though it's in the docs
    return <Navigate to={url} replace={true} /* what does this do? */ />;
  }

  // console.log(window.props_w = props);
  return (
    <Routes>
      {/*<Route path="/help" element={<HelpWidget/>} />*/}
      <Route path="/" element={<App/>}>
        <Route
            path="cset-comparison"
            element={<CsetComparisonPage/>}
        />
        <Route
            path="OMOPConceptSets"
            element={<ConceptSetsPage/>}
        />
        <Route path="about" element={<AboutPage/>} />
        <Route path="upload-csv" element={<UploadCsvPage/>} />
        <Route
            path="graph"
            element={<ConceptGraph/>}
        />
        {/*<Route path="download-json" element={<DownloadJSON/>} />*/}
        <Route path="view-state" element={<ViewCurrentState/>} />
        {/* <Route path="OMOPConceptSet/:conceptId" element={<OldConceptSet />} /> */}
      </Route>
    </Routes>
  );
}
function App(props) {
  const alerts = useAlerts();
  const alertsDispatch = useAlertsDispatch();

  return (
    <ThemeProvider theme={theme}>
      {/*
        <Box sx={{backgroundColor: '#EEE', border: '2px solid green', minWidth: '200px', minHeight: '200px'}} >
          // <ContentItems/>
        </Box>
        */}
      <div className="App">
        {/* <ReactQueryDevtools initialIsOpen={false} />*/}
        <MuiAppBar>
          {/* Outlet: Will render the results of whatever nested route has been clicked/activated. */}
        </MuiAppBar>
        <AlertMessages alerts={alerts}/>
        <Outlet />
      </div>
    </ThemeProvider>
  );
}
const theme = createTheme({
  // https://mui.com/material-ui/customization/theme-components/#global-style-overrides
  // https://mui.com/material-ui/guides/interoperability/#global-css
  // see example https://mui.com/material-ui/customization/theming/
  // status: { danger: orange[500], },
  components: {
    MuiCard: {
      defaultProps: {
        margin: "6pt",
      },
    },
  },
});

/*
when in doubt: https://reactjs.org/docs/hooks-reference.html and https://reactrouter.com/docs/en/v6

just found this: https://betterprogramming.pub/why-you-should-be-separating-your-server-cache-from-your-ui-state-1585a9ae8336
All the stuff below was from trying to find a solution to fetching data and using it across components

https://reactjs.org/docs/hooks-reference.html#useref
  React guarantees that setState function identity is stable and won’t change on re-renders.
  This is why it’s safe to omit from the useEffect or useCallback dependency list.

cool: https://reactjs.org/docs/hooks-reference.html#useref
  If the new state is computed using the previous state, you can pass
  a function to setState.The function will receive the previous
  value, and return an updated value.
     const [count, setCount] = useState(initialCount);
     <button onClick={() => setCount(initialCount)}>Reset</button>           // set with static value
     <button onClick={() => setCount(prevCount => prevCount - 1)}>-</button> // set with function

https://reactjs.org/docs/hooks-reference.html#conditionally-firing-an-effect
  The default behavior for effects is to fire the effect after every completed render.
  However, this may be overkill in some cases, like the subscription example from the
    previous section. We don’t need to create a new subscription on every update, only
    if the source prop has changed.... To implement this, pass a second argument to
    useEffect that is the array of values that the effect depends on.
OH!! Does that mean: without a dependency list, the useEffects function will run on every render?

*/

export { QCProvider };
