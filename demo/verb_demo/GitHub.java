import java.io.IOException;
import java.util.List;

/**
 * GitHub Repository API interface
 * Provides methods to interact with GitHub's REST API for repository operations
 */
public interface GitHub {
    /**
     * List organization repositories
     * @param org The organization name
     * @param type Filter by repository type: "all", "public", "private", "forks", "sources", "member"
     * @param sort Sort by: "created", "updated", "pushed", "full_name"
     * @param direction Sort direction: "asc" or "desc"
     * @param perPage Number of results per page (1-100)
     * @param page Page number to retrieve
     * @return List of repository information
     */
    List<String> listOrganizationRepositories(String org, String type, String sort, 
                                            String direction, Integer perPage, Integer page);
    
    /**
     * Create an organization repository (displays request without sending)
     * @param org The organization name
     * @param name Repository name
     * @param description Repository description
     * @param isPrivate Whether the repository should be private
     * @param hasIssues Whether issues are enabled
     * @param hasProjects Whether projects are enabled
     * @param hasWiki Whether wiki is enabled
     * @param autoInit Whether to initialize with README
     * @param gitignoreTemplate Gitignore template to use
     * @param licenseTemplate License template to use
     * @return List of repository creation information
     */
    List<String> createOrganizationRepository(String org, String name, String description, 
                                            boolean isPrivate, boolean hasIssues, 
                                            boolean hasProjects, boolean hasWiki, 
                                            boolean autoInit, String gitignoreTemplate, 
                                            String licenseTemplate);
    
    /**
     * Get a repository
     * @param owner The repository owner (user or organization)
     * @param repo The repository name
     * @return List of repository information
     */
    List<String> getRepository(String owner, String repo);
    
    /**
     * List issues in a repository
     * @param owner The repository owner (user or organization)
     * @param repo The repository name
     * @param milestone Filter by milestone ("none", "*", or milestone number)
     * @param state Filter by state: "open", "closed", "all"
     * @param assignee Filter by assignee ("none", "*", or username)
     * @param creator Filter by creator username
     * @param mentioned Filter by mentioned username
     * @param labels Filter by comma-separated list of label names
     * @param sort Sort by: "created", "updated", "comments"
     * @param direction Sort direction: "asc" or "desc"
     * @param since Only issues updated after this timestamp (ISO 8601 format)
     * @param perPage Number of results per page (1-100)
     * @param page Page number to retrieve
     * @return List of issue information
     */
    List<String> listRepositoryIssues(String owner, String repo, String milestone, 
                                     String state, String assignee, String creator, 
                                     String mentioned, String labels, String sort, 
                                     String direction, String since, Integer perPage, Integer page);
        
    /**
     * Convenience method to list open issues in a repository
     * @param owner The repository owner (user or organization)
     * @param repo The repository name
     * @param perPage Number of results per page (1-100)
     * @return List of issue information
     */
    List<String> listOpenIssues(String owner, String repo, Integer perPage);
    
    /**
     * Convenience method to list issues by assignee
     * @param owner The repository owner (user or organization)
     * @param repo The repository name
     * @param assignee The assignee username ("none" for unassigned, "*" for any assigned)
     * @param perPage Number of results per page (1-100)
     * @return List of issue information
     */
    List<String> listIssuesByAssignee(String owner, String repo, String assignee, Integer perPage);

    /**
     * Convenience method to list organization repositories with default parameters
     * @param org The organization name
     * @return List of repository information
     */
    List<String> listOrganizationRepositories(String org);
    
    /**
     * Convenience method to create a simple public repository
     * @param org The organization name
     * @param name Repository name
     * @param description Repository description
     * @return List of repository creation information
     */
    List<String> createSimpleRepository(String org, String name, String description);
    
    /**
     * Convenience method to create a private repository with common settings
     * @param org The organization name
     * @param name Repository name
     * @param description Repository description
     * @return List of repository creation information
     */
    List<String> createPrivateRepository(String org, String name, String description);
}
